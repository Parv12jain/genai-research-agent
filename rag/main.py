import os
import ast
import streamlit as st

from pathlib import Path

from dotenv import load_dotenv
from rich import print

from langchain_mistralai import ChatMistralAI
from langchain_chroma import Chroma

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import ToolMessage

from langchain.tools import tool
from langchain.agents import create_agent

from tavily import TavilyClient


# ============================================================
# 2. ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()


# ============================================================
# 3. PROJECT PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

PAPERS = BASE_DIR.parent / "papers"


# ============================================================
# 4. TAVILY CLIENT
# ============================================================

# Tavily is used for LIVE WEB SEARCH.
#
# We use it when the agent needs:
# - latest information
# - current information
# - recent developments
# - information outside our research papers

tavily_client = TavilyClient(
    api_key=os.getenv("TAVILY_API_KEY")
)


# ============================================================
# 5. LOAD PDF RESEARCH PAPERS
# ============================================================

pdf_files = list(
    PAPERS.glob("*.pdf")
)

documents = []


for pdf in pdf_files:

    loader = PyPDFLoader(
        str(pdf)
    )

    documents.extend(
        loader.load()
    )


print(
    f"\nLoaded {len(pdf_files)} PDF files."
)

print(
    f"Loaded {len(documents)} pages."
)


# ============================================================
# 6. SPLIT DOCUMENTS INTO CHUNKS
# ============================================================

# Large documents are divided into smaller chunks.
#
# Why?
#
# The embedding model and retriever work better when
# searching smaller meaningful pieces of text instead
# of entire PDF pages/documents.

splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200
)


chunks = splitter.split_documents(
    documents
)


print(
    f"Created {len(chunks)} chunks."
)


# ============================================================
# 7. CREATE EMBEDDINGS
# ============================================================

# ============================================================
# 7. CREATE EMBEDDINGS
# ============================================================

@st.cache_resource
def load_embeddings():
    print("Loading embedding model...")
    
    return HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-mpnet-base-v2"
    )

embeddings_model = load_embeddings()

# ============================================================
# 8. CREATE CHROMA VECTOR DATABASE
# ============================================================

# Chroma stores:
#
#     chunk text
#     +
#     embeddings
#     +
#     metadata
#
# Metadata includes things such as PDF filename and page.

# ============================================================
# 8. CREATE / LOAD CHROMA VECTOR DATABASE
# ============================================================

@st.cache_resource
def load_vectorstore():

    print("Loading Chroma database...")

    chroma_path = str(BASE_DIR.parent / "chroma_db")

    # Try loading existing Chroma database
    vectorstore = Chroma(
        persist_directory=chroma_path,
        embedding_function=embeddings_model
    )

    # Check whether database already contains documents
    try:
        count = vectorstore._collection.count()
    except Exception:
        count = 0

    # If database is empty, create embeddings and add documents
    if count == 0:

        print("Chroma database is empty.")
        print("Creating embeddings for PDF chunks...")

        vectorstore = Chroma.from_documents(
            documents=chunks,
            embedding=embeddings_model,
            persist_directory=chroma_path
        )

        print("Chroma database created.")

    else:

        print(f"Loaded existing Chroma database with {count} chunks.")

    return vectorstore


vectorstore = load_vectorstore()

# ============================================================
# 9. CREATE MMR RETRIEVER
# ============================================================

# MMR = Maximum Marginal Relevance
#
# Instead of simply returning the most similar chunks,
# MMR tries to return chunks that are:
#
#     relevant to the question
#     +
#     diverse from each other
#
# fetch_k = 10
#     → first consider 10 candidate chunks
#
# k = 4
#     → finally return 4 chunks
#
# lambda_mult = 0.7
#     → balances relevance and diversity

retriever = vectorstore.as_retriever(

    search_type="mmr",

    search_kwargs={

        "k": 4,

        "fetch_k": 10,

        "lambda_mult": 0.7
    }
)


# ============================================================
# 10. CONNECT TO MISTRAL
# ============================================================

# ============================================================
# 10. CONNECT TO MISTRAL
# ============================================================

@st.cache_resource
def load_llm():

    print("Loading Mistral LLM...")

    return ChatMistralAI(
        model="mistral-medium-3-5",
        temperature=0
    )


llm = load_llm()

# ============================================================
# 11. RAG PROMPT
# ============================================================

# This prompt controls how the LLM answers questions
# using retrieved research-paper context.

prompt = ChatPromptTemplate.from_template(
"""
You are a research assistant answering questions using a collection
of research papers.

Use ONLY the provided context to answer the question.

Rules:

- Do not invent facts that are not supported by the context.
- Give a clear and technically accurate answer.
- If the context does not contain enough information, say:
  "I couldn't find enough information in the provided papers."
- When useful, explain concepts with short bullet points.
- Do not mention the retrieval process in your answer.
- Do not ask follow-up questions at the end.
- Do not offer additional explanations, examples, comparisons, or code
  unless the user explicitly asks for them.
- End your response after answering the user's question.

Context:
{context}

Question:
{question}

Answer:
"""
)


# ============================================================
# 12. RETRIEVE CONTEXT
# ============================================================

def retrieve_context(question):
    """
    Retrieve relevant and diverse chunks from the research papers.

    Flow:

        Question
            ↓
        MMR Retriever
            ↓
        Relevant Chunks
            ↓
        Context

    Returns:
        context -> text given to the LLM
        docs    -> original documents with metadata
    """

    # MMR retrieval happens here.
    docs = retriever.invoke(
        question
    )

    # Convert retrieved chunks into one text block.
    context = "\n\n".join(
        doc.page_content
        for doc in docs
    )

    return context, docs


# ============================================================
# 13. ASK RAG
# ============================================================

def ask_rag(question):
    """
    Complete RAG pipeline.

    Question
        ↓
    MMR Retrieval
        ↓
    Retrieved Context
        ↓
    RAG Prompt
        ↓
    Mistral
        ↓
    Answer
    """

    context, docs = retrieve_context(
        question
    )

    messages = prompt.invoke(
        {
            "context": context,
            "question": question
        }
    )

    response = llm.invoke(
        messages
    )

    return response.content, docs


# ============================================================
# 14. FORMAT PDF SOURCES
# ============================================================

def format_sources(docs):
    """
    Convert PDF metadata into a clean human-readable source.

    Example:

        C:/project/papers/attention.pdf
                         ↓
        attention.pdf — Page 4
    """

    sources = []

    for doc in docs:

        # Get only filename instead of the entire path.
        filename = Path(
            doc.metadata.get(
                "source",
                ""
            )
        ).name

        # PyPDFLoader uses zero-based page numbers.
        page = doc.metadata.get(
            "page"
        )

        source = (
            f"{filename} — "
            f"Page "
            f"{page + 1 if page is not None else 'Unknown'}"
        )

        # Avoid duplicate PDF/page sources.
        if source not in sources:

            sources.append(
                source
            )

    return sources


# ============================================================
# 15. RESEARCH PAPERS TOOL
# ============================================================

# @tool converts this normal Python function into a
# LangChain tool.
#
# The Research Agent can now decide:
#
#     "I need information from the research papers."
#
# and call this function automatically.

@tool
def research_papers(question: str):
    """
    Search the user's uploaded research papers.

    Use this tool whenever the question asks about:
    - information contained in the uploaded papers
    - specific research papers
    - paper findings
    - paper architecture
    - paper methodology
    - paper experiments
    - paper results
    - concepts that should be answered from the research papers

    This tool performs RAG retrieval using the research-paper collection.
    """

    # Run our existing RAG pipeline.
    answer, docs = ask_rag(
        question
    )

    # Format PDF/page sources.
    sources = format_sources(
        docs
    )

    return {
        "answer": answer,
        "sources": sources
    }


# ============================================================
# 16. FORMAT WEB SOURCES
# ============================================================

def format_web_sources(results):
    """
    Convert Tavily results into a clean source structure.

    This makes the results easier to use later in the UI.
    """

    sources = []

    for result in results:

        source = {
            "title": result.get(
                "title",
                "Unknown"
            ),

            "url": result.get(
                "url",
                ""
            )
        }

        # Avoid duplicate sources.
        if source not in sources:

            sources.append(
                source
            )

    return sources


# ============================================================
# 17. WEB SEARCH TOOL
# ============================================================

# This is our second tool.
#
# research_papers → private/local research knowledge
#
# web_search      → live/current internet information

@tool
def web_search(query: str):
    """
    Search the live web for current, recent,
    latest, or internet-based information.
    """

    response = tavily_client.search(

        query=query,

        search_depth="advanced",

        max_results=5
    )

    results = []

    for result in response.get(
        "results",
        []
    ):

        results.append(
            {
                "title": result.get(
                    "title"
                ),

                "url": result.get(
                    "url"
                ),

                "content": result.get(
                    "content"
                )
            }
        )

    # Create clean source list.
    sources = format_web_sources(
        results
    )

    return {
        "query": query,

        "results": results,

        "sources": sources
    }


# ============================================================
# 18.5. DETECT TIME-SENSITIVE QUESTIONS
# ============================================================

TIME_SENSITIVE_TERMS = [
    "latest",
    "current",
    "recent",
    "today",
    "newest",
    "recently",
    "this year",
    "this month",
    "what changed",
    "latest update",
    "latest updates",
    "current version",
    "latest version",
    "recent developments",
]


def is_time_sensitive(question):

    question_lower = question.lower()

    return any(
        term in question_lower
        for term in TIME_SENSITIVE_TERMS
    )


# ============================================================
# 18. EXTRACT TEXT FROM MISTRAL CONTENT
# ============================================================

def extract_text(content):
    """
    Convert different Mistral content formats into
    one clean string.

    Mistral may return:

        "normal string"

    OR:

        [
            {"type": "text", "text": "..."},
            {"type": "text", "reference": ...}
        ]

    We only keep actual text.
    """

    # --------------------------------------------------------
    # CASE 1: Normal string
    # --------------------------------------------------------

    if isinstance(
        content,
        str
    ):

        return content


    # --------------------------------------------------------
    # CASE 2: List of content blocks
    # --------------------------------------------------------

    if isinstance(
        content,
        list
    ):

        text_parts = []

        for block in content:

            # Make sure this is a dictionary.
            if not isinstance(
                block,
                dict
            ):

                continue

            # Extract only actual text.
            text = block.get(
                "text"
            )

            if isinstance(
                text,
                str
            ):

                text_parts.append(
                    text
                )

        return "".join(
            text_parts
        )


    # --------------------------------------------------------
    # CASE 3: Unexpected format
    # --------------------------------------------------------

    return str(
        content
    )


# ============================================================
# 19. PARSE TOOL RESULT
# ============================================================

def parse_tool_result(content):
    """
    Convert the ToolMessage content back into a Python
    dictionary.

    The tool normally returns a dictionary, but LangChain
    may serialize it before placing it inside ToolMessage.

    We therefore support a few formats.
    """

    # --------------------------------------------------------
    # Already a dictionary
    # --------------------------------------------------------

    if isinstance(
        content,
        dict
    ):

        return content


    # --------------------------------------------------------
    # Python dictionary stored as string
    # --------------------------------------------------------

    if isinstance(
        content,
        str
    ):

        try:

            return ast.literal_eval(
                content
            )

        except (
            ValueError,
            SyntaxError
        ):

            return {}


    return {}


# ============================================================
# 20. FORMAT COMPLETE AGENT RESULT
# ============================================================

def format_agent_result(result):
    """
    Convert the raw LangChain agent result into a clean
    application-ready structure.

    Raw agent result:

        HumanMessage
        AIMessage
        ToolMessage
        AIMessage

    Clean result:

        {
            "answer": "...",
            "sources": [...],
            "tools_used": [...]
        }

    This structure will later be directly consumed
    by the Streamlit UI.
    """

    messages = result.get(
        "messages",
        []
    )

    sources = []

    tools_used = []


    # ========================================================
    # 20.1 FIND FINAL AI MESSAGE
    # ========================================================

    # Usually the last message is the final AI response.
    #
    # We search backwards for an AI message instead of blindly
    # assuming the last message is always the final answer.

    final_message = None

    for message in reversed(
        messages
    ):

        if message.__class__.__name__ == "AIMessage":

            # Make sure this is not simply a tool-call message.
            if not getattr(
                message,
                "tool_calls",
                None
            ):

                final_message = message

                break


    # Fallback: if we didn't find one, use last message.
    if final_message is None and messages:

        final_message = messages[-1]


    # ========================================================
    # 20.2 EXTRACT FINAL ANSWER
    # ========================================================

    if final_message is not None:

        answer = extract_text(
            final_message.content
        )

    else:

        answer = ""


    # ========================================================
    # 20.3 PROCESS TOOL MESSAGES
    # ========================================================

    for message in messages:

        # We only need ToolMessages.
        if not isinstance(
            message,
            ToolMessage
        ):

            continue


        # ----------------------------------------------------
        # Record tool name
        # ----------------------------------------------------

        tool_name = getattr(
            message,
            "name",
            None
        )

        if tool_name:

            if tool_name not in tools_used:

                tools_used.append(
                    tool_name
                )


        # ----------------------------------------------------
        # Parse tool result
        # ----------------------------------------------------

        tool_result = parse_tool_result(
            message.content
        )


        # ----------------------------------------------------
        # Research paper sources
        # ----------------------------------------------------

        if tool_name == "research_papers":

            paper_sources = tool_result.get(
                "sources",
                []
            )

            for source in paper_sources:

                formatted_source = {
                    "type": "paper",
                    "source": source
                }

                if formatted_source not in sources:

                    sources.append(
                        formatted_source
                    )


        # ----------------------------------------------------
        # Web sources
        # ----------------------------------------------------

        elif tool_name == "web_search":

            web_sources = tool_result.get(
                "sources",
                []
            )

            for source in web_sources:

                formatted_source = {
                    "type": "web",
                    "source": source
                }

                if formatted_source not in sources:

                    sources.append(
                        formatted_source
                    )


    # ========================================================
    # 20.4 RETURN CLEAN RESULT
    # ========================================================

    return {
        "answer": answer,
        "sources": sources,
        "tools_used": tools_used
    }


# create_agent() automatically manages:
#
#     LLM
#       ↓
#     tool selection
#       ↓
#     tool execution
#       ↓
#     tool result
#       ↓
#     LLM
#       ↓
#     final answer
#
# We no longer manually handle:
#
#     tool_call
#     ToolMessage creation
#     second LLM call
#
# LangChain's agent handles that workflow.

@st.cache_resource
def load_research_agent():

    print("Creating research agent...")

    return create_agent(
        model=llm,
        tools=[
            research_papers,
            web_search
        ],
        system_prompt="""
You are a research assistant that provides accurate,
evidence-based answers.

You have access to two information sources:

1. research_papers
   - Searches the user's uploaded research papers using RAG + MMR.
   - Use this for questions about the uploaded papers.

2. web_search
   - Searches the live internet.
   - Use this for current, recent, latest, live, or
     internet-based information.

============================================================
TOOL SELECTION RULES
============================================================

PAPER QUESTIONS:

- If the user explicitly mentions a research paper,
  uploaded paper, paper architecture, methodology,
  findings, experiments, or results:

  ALWAYS use research_papers.

CURRENT / TIME-SENSITIVE QUESTIONS:

- If the user uses words such as:
  latest, current, recent, today, newest, new,
  this year, this month, 2026, recently, updates,
  developments, what changed, current version,
  latest version:

  ALWAYS use web_search BEFORE answering.

- NEVER answer a time-sensitive question using your
  internal knowledge alone.

- NEVER describe information as "latest", "current",
  or "recent" unless web_search was actually used.

- When using web_search, prefer recent and authoritative
  sources.

- Check the dates of the sources whenever possible.

- Do not treat an old article or report as a current
  update unless you clearly identify its publication date
  and explain that it is historical information.

- If current information cannot be verified from web
  search, explicitly say that current information could
  not be verified.

COMPARISON QUESTIONS:

- If the user asks to compare uploaded research papers
  with current information:

  ALWAYS use BOTH research_papers and web_search.

GENERAL QUESTIONS:

- For general questions that are not paper-specific and
  are not time-sensitive, you may answer using your
  general knowledge or use web_search when useful.

============================================================
ANSWER RULES
============================================================

- Base factual claims on the evidence returned by the
  tools whenever tools are used.

- Do not invent sources, dates, versions, statistics,
  or facts.

- For web-based answers, include the important sources
  used.

- Clearly distinguish historical information from current
  information.

- If sources disagree, mention the disagreement rather
  than silently choosing one.

- Never claim that information is current unless it was
  verified through web search.

After receiving tool results, synthesize the evidence
into a clear and concise final answer.
"""
)


research_agent = load_research_agent()




