# import os
# import ast
# import streamlit as st
# import requests
# from pathlib import Path
# import requests
# from dotenv import load_dotenv
# from rich import print

# from langchain_mistralai import ChatMistralAI
# from langchain_chroma import Chroma

# from langchain_community.document_loaders import PyPDFLoader
# from langchain_text_splitters import RecursiveCharacterTextSplitter
# from langchain_huggingface import HuggingFaceEmbeddings

# from langchain_core.prompts import ChatPromptTemplate
# from langchain_core.messages import ToolMessage

# from langchain.tools import tool
# from langchain.agents import create_agent

# from tavily import TavilyClient


# # ============================================================
# # 2. ENVIRONMENT VARIABLES
# # ============================================================

# load_dotenv()


# # ============================================================
# # 3. PROJECT PATHS
# # ============================================================

# BASE_DIR = Path(__file__).resolve().parent

# PAPERS = BASE_DIR.parent / "papers"


# # ============================================================
# # 4. TAVILY CLIENT
# # ============================================================

# # Tavily is used for LIVE WEB SEARCH.
# #
# # We use it when the agent needs:
# # - latest information
# # - current information
# # - recent developments
# # - information outside our research papers

# tavily_client = TavilyClient(
#     api_key=os.getenv("TAVILY_API_KEY")
# )


# # ============================================================
# # 5. LOAD PDF RESEARCH PAPERS
# # ============================================================

# pdf_files = list(
#     PAPERS.glob("*.pdf")
# )

# documents = []


# for pdf in pdf_files:

#     loader = PyPDFLoader(
#         str(pdf)
#     )

#     documents.extend(
#         loader.load()
#     )


# print(
#     f"\nLoaded {len(pdf_files)} PDF files."
# )

# print(
#     f"Loaded {len(documents)} pages."
# )


# # ============================================================
# # 6. SPLIT DOCUMENTS INTO CHUNKS
# # ============================================================

# # Large documents are divided into smaller chunks.
# #
# # Why?
# #
# # The embedding model and retriever work better when
# # searching smaller meaningful pieces of text instead
# # of entire PDF pages/documents.

# splitter = RecursiveCharacterTextSplitter(
#     chunk_size=1000,
#     chunk_overlap=200
# )


# chunks = splitter.split_documents(
#     documents
# )


# print(
#     f"Created {len(chunks)} chunks."
# )


# # ============================================================
# # 7. CREATE EMBEDDINGS
# # ============================================================

# # ============================================================
# # 7. CREATE EMBEDDINGS
# # ============================================================

# @st.cache_resource
# def load_embeddings():
#     print("Loading embedding model...")
    
#     return HuggingFaceEmbeddings(
#         model_name="sentence-transformers/all-mpnet-base-v2"
#     )

# embeddings_model = load_embeddings()

# # ============================================================
# # 8. CREATE CHROMA VECTOR DATABASE
# # ============================================================

# # Chroma stores:
# #
# #     chunk text
# #     +
# #     embeddings
# #     +
# #     metadata
# #
# # Metadata includes things such as PDF filename and page.

# # ============================================================
# # 8. CREATE / LOAD CHROMA VECTOR DATABASE
# # ============================================================

# @st.cache_resource
# def load_vectorstore():

#     print("Loading Chroma database...")

#     chroma_path = str(BASE_DIR.parent / "chroma_db")

#     # Try loading existing Chroma database
#     vectorstore = Chroma(
#         persist_directory=chroma_path,
#         embedding_function=embeddings_model
#     )

#     # Check whether database already contains documents
#     try:
#         count = vectorstore._collection.count()
#     except Exception:
#         count = 0

#     # If database is empty, create embeddings and add documents
#     if count == 0:

#         print("Chroma database is empty.")
#         print("Creating embeddings for PDF chunks...")

#         vectorstore = Chroma.from_documents(
#             documents=chunks,
#             embedding=embeddings_model,
#             persist_directory=chroma_path
#         )

#         print("Chroma database created.")

#     else:

#         print(f"Loaded existing Chroma database with {count} chunks.")

#     return vectorstore


# vectorstore = load_vectorstore()

# # ============================================================
# # 9. CREATE MMR RETRIEVER
# # ============================================================

# # MMR = Maximum Marginal Relevance
# #
# # Instead of simply returning the most similar chunks,
# # MMR tries to return chunks that are:
# #
# #     relevant to the question
# #     +
# #     diverse from each other
# #
# # fetch_k = 10
# #     → first consider 10 candidate chunks
# #
# # k = 4
# #     → finally return 4 chunks
# #
# # lambda_mult = 0.7
# #     → balances relevance and diversity

# retriever = vectorstore.as_retriever(

#     search_type="mmr",

#     search_kwargs={

#         "k": 4,

#         "fetch_k": 10,

#         "lambda_mult": 0.7
#     }
# )


# # ============================================================
# # 10. CONNECT TO MISTRAL
# # ============================================================

# # ============================================================
# # 10. CONNECT TO MISTRAL
# # ============================================================

# @st.cache_resource
# def load_llm():

#     print("Loading Mistral LLM...")

#     return ChatMistralAI(
#         model="mistral-medium-3-5",
#         temperature=0
#     )


# llm = load_llm()

# # ============================================================
# # 11. RAG PROMPT
# # ============================================================

# # This prompt controls how the LLM answers questions
# # using retrieved research-paper context.

# prompt = ChatPromptTemplate.from_template(
# """
# You are a research assistant answering questions using a collection
# of research papers.

# Use ONLY the provided context to answer the question.

# Rules:

# - Do not invent facts that are not supported by the context.
# - Give a clear and technically accurate answer.
# - If the context does not contain enough information, say:
#   "I couldn't find enough information in the provided papers."
# - When useful, explain concepts with short bullet points.
# - Do not mention the retrieval process in your answer.
# - Do not ask follow-up questions at the end.
# - Do not offer additional explanations, examples, comparisons, or code
#   unless the user explicitly asks for them.
# - End your response after answering the user's question.

# Context:
# {context}

# Question:
# {question}

# Answer:
# """
# )


# # ============================================================
# # 12. RETRIEVE CONTEXT
# # ============================================================

# def retrieve_context(question):
#     """
#     Retrieve relevant and diverse chunks from the research papers.

#     Flow:

#         Question
#             ↓
#         MMR Retriever
#             ↓
#         Relevant Chunks
#             ↓
#         Context

#     Returns:
#         context -> text given to the LLM
#         docs    -> original documents with metadata
#     """

#     # MMR retrieval happens here.
#     docs = retriever.invoke(
#         question
#     )

#     # Convert retrieved chunks into one text block.
#     context = "\n\n".join(
#         doc.page_content
#         for doc in docs
#     )

#     return context, docs


# # ============================================================
# # 13. ASK RAG
# # ============================================================

# def ask_rag(question):
#     """
#     Complete RAG pipeline.

#     Question
#         ↓
#     MMR Retrieval
#         ↓
#     Retrieved Context
#         ↓
#     RAG Prompt
#         ↓
#     Mistral
#         ↓
#     Answer
#     """

#     context, docs = retrieve_context(
#         question
#     )

#     messages = prompt.invoke(
#         {
#             "context": context,
#             "question": question
#         }
#     )

#     response = llm.invoke(
#         messages
#     )

#     return response.content, docs


# # ============================================================
# # 14. FORMAT PDF SOURCES
# # ============================================================

# def format_sources(docs):
#     """
#     Convert PDF metadata into a clean human-readable source.

#     Example:

#         C:/project/papers/attention.pdf
#                          ↓
#         attention.pdf — Page 4
#     """

#     sources = []

#     for doc in docs:

#         # Get only filename instead of the entire path.
#         filename = Path(
#             doc.metadata.get(
#                 "source",
#                 ""
#             )
#         ).name

#         # PyPDFLoader uses zero-based page numbers.
#         page = doc.metadata.get(
#             "page"
#         )

#         source = (
#             f"{filename} — "
#             f"Page "
#             f"{page + 1 if page is not None else 'Unknown'}"
#         )

#         # Avoid duplicate PDF/page sources.
#         if source not in sources:

#             sources.append(
#                 source
#             )

#     return sources


# # ============================================================
# # 15. RESEARCH PAPERS TOOL
# # ============================================================

# # @tool converts this normal Python function into a
# # LangChain tool.
# #
# # The Research Agent can now decide:
# #
# #     "I need information from the research papers."
# #
# # and call this function automatically.

# @tool
# def research_papers(question: str):
#     """
#     Search the user's uploaded research papers and return
#     the answer together with the exact PDF/page sources.
#     """

#     answer, docs = ask_rag(question)

#     sources = format_sources(docs)

#     source_text = "\n".join(
#         f"- {source}"
#         for source in sources
#     )

#     return {
#         "answer": answer,
#         "sources": sources,
#         "source_text": source_text
#     }


# # ============================================================
# # 16. FORMAT WEB SOURCES
# # ============================================================

# def format_web_sources(results):
#     """
#     Convert Tavily results into a clean source structure.

#     This makes the results easier to use later in the UI.
#     """

#     sources = []

#     for result in results:

#         source = {
#             "title": result.get(
#                 "title",
#                 "Unknown"
#             ),

#             "url": result.get(
#                 "url",
#                 ""
#             )
#         }

#         # Avoid duplicate sources.
#         if source not in sources:

#             sources.append(
#                 source
#             )

#     return sources


# # ============================================================
# # 17. WEB SEARCH TOOL
# # ============================================================

# # This is our second tool.
# #
# # research_papers → private/local research knowledge
# #
# # web_search      → live/current internet information

# @tool
# def web_search(query: str):
#     """
#     Search the live web for current, recent,
#     latest, or internet-based information.
#     """

#     try:

#         response = tavily_client.search(
#             query=query,
#             search_depth="advanced",
#             max_results=5
#         )

#     except requests.exceptions.RequestException as e:

#         return {
#             "query": query,
#             "results": [],
#             "sources": [],
#             "error": (
#                 "Live web search is temporarily unavailable. "
#                 "Please try again later."
#             )
#         }

#     except Exception as e:

#         return {
#             "query": query,
#             "results": [],
#             "sources": [],
#             "error": (
#                 "Live web search failed unexpectedly."
#             )
#         }


#     results = []

#     for result in response.get(
#         "results",
#         []
#     ):

#         results.append(
#             {
#                 "title": result.get("title"),
#                 "url": result.get("url"),
#                 "content": result.get("content")
#             }
#         )


#     sources = format_web_sources(
#         results
#     )


#     return {
#         "query": query,
#         "results": results,
#         "sources": sources
#     }

# # ============================================================
# # 18.5. DETECT TIME-SENSITIVE QUESTIONS
# # ============================================================

# TIME_SENSITIVE_TERMS = [
#     "latest",
#     "current",
#     "recent",
#     "today",
#     "newest",
#     "recently",
#     "this year",
#     "this month",
#     "what changed",
#     "latest update",
#     "latest updates",
#     "current version",
#     "latest version",
#     "recent developments",
# ]


# def is_time_sensitive(question):

#     question_lower = question.lower()

#     return any(
#         term in question_lower
#         for term in TIME_SENSITIVE_TERMS
#     )

# PAPER_TERMS = [
#     "paper",
#     "research paper",
#     "according to the paper",
#     "from the paper",
#     "in the paper",
#     "architecture",
#     "methodology",
#     "experiment",
#     "experiments",
#     "results",
#     "findings",
#     "proposed",
#     "according to",
#     "gru",
#     "bert",
#     "rag",
#     "attention",
#     "transformer",
#     "react",
#     "few shot",
#     "few-shot",
# ]


# def is_paper_question(question):

#     question_lower = question.lower()

#     return any(
#         term in question_lower
#         for term in PAPER_TERMS
#     )


# # ============================================================
# # 18. EXTRACT TEXT FROM MISTRAL CONTENT
# # ============================================================

# def extract_text(content):
#     """
#     Convert different Mistral content formats into
#     one clean string.

#     Mistral may return:

#         "normal string"

#     OR:

#         [
#             {"type": "text", "text": "..."},
#             {"type": "text", "reference": ...}
#         ]

#     We only keep actual text.
#     """

#     # --------------------------------------------------------
#     # CASE 1: Normal string
#     # --------------------------------------------------------

#     if isinstance(
#         content,
#         str
#     ):

#         return content


#     # --------------------------------------------------------
#     # CASE 2: List of content blocks
#     # --------------------------------------------------------

#     if isinstance(
#         content,
#         list
#     ):

#         text_parts = []

#         for block in content:

#             # Make sure this is a dictionary.
#             if not isinstance(
#                 block,
#                 dict
#             ):

#                 continue

#             # Extract only actual text.
#             text = block.get(
#                 "text"
#             )

#             if isinstance(
#                 text,
#                 str
#             ):

#                 text_parts.append(
#                     text
#                 )

#         return "".join(
#             text_parts
#         )


#     # --------------------------------------------------------
#     # CASE 3: Unexpected format
#     # --------------------------------------------------------

#     return str(
#         content
#     )


# # ============================================================
# # 19. PARSE TOOL RESULT
# # ============================================================

# def parse_tool_result(content):
#     """
#     Convert ToolMessage content into a Python dictionary.

#     Supports:
#     - dict
#     - Python dictionary string
#     - JSON dictionary string
#     """

#     # --------------------------------------------------------
#     # Already a dictionary
#     # --------------------------------------------------------

#     if isinstance(
#         content,
#         dict
#     ):

#         return content


#     # --------------------------------------------------------
#     # String content
#     # --------------------------------------------------------

#     if isinstance(
#         content,
#         str
#     ):

#         # Try Python dictionary format
#         try:

#             result = ast.literal_eval(
#                 content
#             )

#             if isinstance(
#                 result,
#                 dict
#             ):

#                 return result

#         except (
#             ValueError,
#             SyntaxError
#         ):

#             pass


#         # Try JSON format
#         try:

#             import json

#             result = json.loads(
#                 content
#             )

#             if isinstance(
#                 result,
#                 dict
#             ):

#                 return result

#         except (
#             ValueError,
#             TypeError
#         ):

#             pass


#     # --------------------------------------------------------
#     # Unsupported format
#     # --------------------------------------------------------

#     return {}

# # ============================================================
# # 20. FORMAT COMPLETE AGENT RESULT
# # ============================================================

# def format_agent_result(result):
#     """
#     Convert the raw LangChain agent result into a clean
#     application-ready structure.

#     Returns:
#         {
#             "answer": "...",
#             "sources": [...],
#             "tools_used": [...]
#         }
#     """

#     messages = result.get(
#         "messages",
#         []
#     )

#     sources = []

#     tools_used = []


#     # ========================================================
#     # FIND FINAL AI ANSWER
#     # ========================================================

#     final_message = None

#     for message in reversed(messages):

#         if message.__class__.__name__ == "AIMessage":

#             if not getattr(
#                 message,
#                 "tool_calls",
#                 None
#             ):

#                 final_message = message

#                 break


#     if final_message is None and messages:

#         final_message = messages[-1]


#     # ========================================================
#     # EXTRACT ANSWER
#     # ========================================================

#     if final_message is not None:

#         answer = extract_text(
#             final_message.content
#         )

#     else:

#         answer = ""


#     # ========================================================
#     # PROCESS TOOL RESULTS
#     # ========================================================

#     for message in messages:

#         if not isinstance(
#             message,
#             ToolMessage
#         ):

#             continue


#         # ----------------------------------------------------
#         # TOOL NAME
#         # ----------------------------------------------------

#         tool_name = getattr(
#             message,
#             "name",
#             None
#         )

#         if tool_name:

#             if tool_name not in tools_used:

#                 tools_used.append(
#                     tool_name
#                 )


#         # ----------------------------------------------------
#         # PARSE TOOL RESULT
#         # ----------------------------------------------------

#         tool_result = parse_tool_result(
#             message.content
#         )


#         if not isinstance(
#             tool_result,
#             dict
#         ):

#             continue


#         # ====================================================
#         # RESEARCH PAPER SOURCES
#         # ====================================================

#         if tool_name == "research_papers":

#             paper_sources = tool_result.get(
#                 "sources",
#                 []
#             )


#             for source in paper_sources:

#                 formatted_source = {
#                     "type": "paper",
#                     "source": source
#                 }


#                 if formatted_source not in sources:

#                     sources.append(
#                         formatted_source
#                     )


#         # ====================================================
#         # WEB SOURCES
#         # ====================================================

#         elif tool_name == "web_search":

#             web_sources = tool_result.get(
#                 "sources",
#                 []
#             )


#             for source in web_sources:

#                 formatted_source = {
#                     "type": "web",
#                     "source": source
#                 }


#                 if formatted_source not in sources:

#                     sources.append(
#                         formatted_source
#                     )


#     # ========================================================
#     # RETURN CLEAN RESULT
#     # ========================================================

#     return {

#         "answer": answer,

#         "sources": sources,

#         "tools_used": tools_used

#     }


#     # ========================================================
#     # 20.1 FIND FINAL AI MESSAGE
#     # ========================================================

#     # Usually the last message is the final AI response.
#     #
#     # We search backwards for an AI message instead of blindly
#     # assuming the last message is always the final answer.

#     final_message = None

#     for message in reversed(
#         messages
#     ):

#         if message.__class__.__name__ == "AIMessage":

#             # Make sure this is not simply a tool-call message.
#             if not getattr(
#                 message,
#                 "tool_calls",
#                 None
#             ):

#                 final_message = message

#                 break


#     # Fallback: if we didn't find one, use last message.
#     if final_message is None and messages:

#         final_message = messages[-1]


#     # ========================================================
#     # 20.2 EXTRACT FINAL ANSWER
#     # ========================================================

#     if final_message is not None:

#         answer = extract_text(
#             final_message.content
#         )

#     else:

#         answer = ""


#     # ========================================================
#     # 20.3 PROCESS TOOL MESSAGES
#     # ========================================================

#     for message in messages:

#         # We only need ToolMessages.
#         if not isinstance(
#             message,
#             ToolMessage
#         ):

#             continue


#         # ----------------------------------------------------
#         # Record tool name
#         # ----------------------------------------------------

#         tool_name = getattr(
#             message,
#             "name",
#             None
#         )

#         if tool_name:

#             if tool_name not in tools_used:

#                 tools_used.append(
#                     tool_name
#                 )


#         # ----------------------------------------------------
#         # Parse tool result
#         # ----------------------------------------------------

#         tool_result = parse_tool_result(
#             message.content
#         )


#         # ----------------------------------------------------
#         # Research paper sources
#         # ----------------------------------------------------

#         if tool_name == "research_papers":

#             paper_sources = tool_result.get(
#                 "sources",
#                 []
#             )

#             for source in paper_sources:

#                 formatted_source = {
#                     "type": "paper",
#                     "source": source
#                 }

#                 if formatted_source not in sources:

#                     sources.append(
#                         formatted_source
#                     )


#         # ----------------------------------------------------
#         # Web sources
#         # ----------------------------------------------------

#         elif tool_name == "web_search":

#             web_sources = tool_result.get(
#                 "sources",
#                 []
#             )

#             for source in web_sources:

#                 formatted_source = {
#                     "type": "web",
#                     "source": source
#                 }

#                 if formatted_source not in sources:

#                     sources.append(
#                         formatted_source
#                     )


#     # ========================================================
#     # 20.4 RETURN CLEAN RESULT
#     # ========================================================

#     return {
#         "answer": answer,
#         "sources": sources,
#         "tools_used": tools_used
#     }


# # create_agent() automatically manages:
# #
# #     LLM
# #       ↓
# #     tool selection
# #       ↓
# #     tool execution
# #       ↓
# #     tool result
# #       ↓
# #     LLM
# #       ↓
# #     final answer
# #
# # We no longer manually handle:
# #
# #     tool_call
# #     ToolMessage creation
# #     second LLM call
# #
# # LangChain's agent handles that workflow.

# @st.cache_resource
# def load_research_agent():

#     print("Creating research agent...")

#     return create_agent(
#         model=llm,
#         tools=[
#             research_papers,
#             web_search
#         ],
#         system_prompt="""
# You are a research assistant that provides accurate,
# evidence-based answers.

# You have access to two information sources:

# 1. research_papers
#    - Searches the user's uploaded research papers using RAG + MMR.
#    - Use this for questions about the uploaded papers.

# 2. web_search
#    - Searches the live internet.
#    - Use this for current, recent, latest, live, or
#      internet-based information.

# ============================================================
# TOOL SELECTION RULES
# ============================================================

# PAPER QUESTIONS:

# - If the user explicitly mentions a research paper,
#   uploaded paper, paper architecture, methodology,
#   findings, experiments, or results:

#   ALWAYS use research_papers.

# CURRENT / TIME-SENSITIVE QUESTIONS:

# - If the user uses words such as:
#   latest, current, recent, today, newest, new,
#   this year, this month, 2026, recently, updates,
#   developments, what changed, current version,
#   latest version:

#   ALWAYS use web_search BEFORE answering.

# - NEVER answer a time-sensitive question using your
#   internal knowledge alone.

# - NEVER describe information as "latest", "current",
#   or "recent" unless web_search was actually used.

# - When using web_search, prefer recent and authoritative
#   sources.

# - Check the dates of the sources whenever possible.

# - Do not treat an old article or report as a current
#   update unless you clearly identify its publication date
#   and explain that it is historical information.

# - If current information cannot be verified from web
#   search, explicitly say that current information could
#   not be verified.

# COMPARISON QUESTIONS:

# - If the user asks to compare uploaded research papers
#   with current information:

#   ALWAYS use BOTH research_papers and web_search.

# GENERAL QUESTIONS:

# - For general questions that are not paper-specific and
#   are not time-sensitive, you may answer using your
#   general knowledge or use web_search when useful.

# ============================================================
# ANSWER RULES
# ============================================================

# - Base factual claims on the evidence returned by the
#   tools whenever tools are used.

# - Do not invent sources, dates, versions, statistics,
#   or facts.

# - For web-based answers, include the important sources
#   used.

# - Clearly distinguish historical information from current
#   information.

# - If sources disagree, mention the disagreement rather
#   than silently choosing one.

# - Never claim that information is current unless it was
#   verified through web search.

# After receiving tool results, synthesize the evidence
# into a clear and concise final answer.
# """
# )


# research_agent = load_research_agent()





import os
import ast
import json
import shutil
import time
from pathlib import Path

import requests
import streamlit as st
from dotenv import load_dotenv
from rich import print

from langchain_mistralai import ChatMistralAI
from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import (
    HumanMessage,
    AIMessage,
    ToolMessage,
)
from langchain.tools import tool
from langchain.agents import create_agent

from tavily import TavilyClient


# ============================================================
# 1. ENVIRONMENT
# ============================================================

load_dotenv()


# ============================================================
# 2. PROJECT PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
PAPERS = BASE_DIR.parent / "papers"
CHROMA_PATH = BASE_DIR.parent / "chroma_db"
CHROMA_MANIFEST = CHROMA_PATH / "pdf_manifest.json"


# ============================================================
# 3. TAVILY CLIENT
# ============================================================

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

if not TAVILY_API_KEY:
    print("WARNING: TAVILY_API_KEY is not configured.")

tavily_client = TavilyClient(
    api_key=TAVILY_API_KEY
) if TAVILY_API_KEY else None


# ============================================================
# 4. LOAD PDF RESEARCH PAPERS
# ============================================================

pdf_files = sorted(PAPERS.glob("*.pdf"))

documents = []

for pdf in pdf_files:
    try:
        loader = PyPDFLoader(str(pdf))
        documents.extend(loader.load())
    except Exception as e:
        print(f"Could not load {pdf.name}: {e}")


print(f"\nLoaded {len(pdf_files)} PDF files.")
print(f"Loaded {len(documents)} pages.")


# ============================================================
# 5. SPLIT DOCUMENTS
# ============================================================

splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
)

chunks = splitter.split_documents(documents)

print(f"Created {len(chunks)} chunks.")


# ============================================================
# 6. EMBEDDINGS
# ============================================================

@st.cache_resource
def load_embeddings():
    print("Loading embedding model...")

    return HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-mpnet-base-v2"
    )


embeddings_model = load_embeddings()


# ============================================================
# 7. CHROMA DATABASE
# ============================================================

@st.cache_resource
def load_vectorstore():

    print("Loading Chroma database...")

    # --------------------------------------------------------
    # No PDF chunks available
    # --------------------------------------------------------

    if not chunks:

        print("No PDF chunks available.")

        return None

    # --------------------------------------------------------
    # Chroma database does not exist
    # --------------------------------------------------------

    if not CHROMA_PATH.exists():

        print("Chroma database does not exist.")

        print("Creating Chroma database from PDFs...")

        vectorstore = Chroma.from_documents(
            documents=chunks,
            embedding=embeddings_model,
            persist_directory=str(CHROMA_PATH),
        )

        print("Chroma database created.")

        return vectorstore

    # --------------------------------------------------------
    # Load existing Chroma database
    # --------------------------------------------------------

    try:

        vectorstore = Chroma(
            persist_directory=str(CHROMA_PATH),
            embedding_function=embeddings_model,
        )

        count = vectorstore._collection.count()

        print(
            f"Loaded Chroma database with {count} chunks."
        )

        return vectorstore

    except Exception as e:

        print(
            f"Could not load Chroma database: {e}"
        )

        st.error(
            "⚠️ Could not load the Chroma database."
        )

        st.info(
            "Stop Streamlit, delete the 'chroma_db' "
            "folder once, and restart the application."
        )

        raise


vectorstore = load_vectorstore()

# ============================================================
# 9. MMR RETRIEVER
# ============================================================

retriever = None

if vectorstore is not None:
    retriever = vectorstore.as_retriever(
        search_type="mmr",
        search_kwargs={
            "k": 4,
            "fetch_k": 10,
            "lambda_mult": 0.7,
        },
    )


# ============================================================
# 10. MISTRAL
# ============================================================

@st.cache_resource
def load_llm():
    print("Loading Mistral LLM...")

    return ChatMistralAI(
        model="mistral-medium-3-5",
        temperature=0,
    )


llm = load_llm()


# ============================================================
# 11. RAG PROMPT
# ============================================================

prompt = ChatPromptTemplate.from_template(
    """
You are a research assistant answering questions using a collection
of uploaded research papers.

Use ONLY the provided context to answer the question.

Rules:

- Do not invent facts that are not supported by the context.
- Give a clear and technically accurate answer.
- If the context does not contain enough information, say:
  "I couldn't find enough information in the provided papers."
- When useful, explain concepts with short bullet points.
- Do not mention the retrieval process.
- Do not claim that information came from a paper unless it is supported
  by the provided context.
- Do not ask follow-up questions.
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
    if retriever is None:
        return "", []

    docs = retriever.invoke(question)

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
    Question
        ↓
    MMR retrieval
        ↓
    PDF chunks
        ↓
    RAG prompt
        ↓
    Mistral
        ↓
    Grounded answer
    """

    context, docs = retrieve_context(question)

    if not docs or not context.strip():
        return (
            "I couldn't find enough information in the provided papers.",
            docs,
        )

    messages = prompt.invoke(
        {
            "context": context,
            "question": question,
        }
    )

    response = llm.invoke(messages)

    return response.content, docs


# ============================================================
# 14. FORMAT PDF SOURCES
# ============================================================

def format_sources(docs):
    sources = []

    for doc in docs:
        filename = Path(
            doc.metadata.get(
                "source",
                "",
            )
        ).name

        page = doc.metadata.get("page")

        source = (
            f"{filename} — Page "
            f"{page + 1 if page is not None else 'Unknown'}"
        )

        if source not in sources:
            sources.append(source)

    return sources


# ============================================================
# 15. RESEARCH PAPERS TOOL
# ============================================================

@tool
def research_papers(question: str):
    """
    Search the user's uploaded research papers.

    This tool performs RAG + MMR retrieval and returns:
    - grounded answer
    - exact PDF/page sources
    """

    answer, docs = ask_rag(question)

    sources = format_sources(docs)

    return {
        "answer": answer,
        "sources": sources,
        "source_text": "\n".join(
            f"- {source}"
            for source in sources
        ),
    }


# ============================================================
# 16. WEB SOURCE FORMATTER
# ============================================================

def format_web_sources(results):
    sources = []

    for result in results:
        source = {
            "title": result.get(
                "title",
                "Unknown",
            ),
            "url": result.get(
                "url",
                "",
            ),
        }

        if source not in sources:
            sources.append(source)

    return sources


# ============================================================
# 17. WEB SEARCH TOOL
# ============================================================

@tool
def web_search(query: str):
    """
    Search the live web for current, recent, latest,
    or internet-based information.
    """

    if tavily_client is None:
        return {
            "query": query,
            "results": [],
            "sources": [],
            "error": "TAVILY_API_KEY is not configured.",
        }

    last_error = None

    # Tavily/network failures can occasionally happen on Streamlit Cloud.
    # Retry a few times before returning a clean tool error.
    for attempt in range(3):
        try:
            response = tavily_client.search(
                query=query,
                search_depth="advanced",
                max_results=5,
            )

            results = []

            for result in response.get("results", []):
                results.append(
                    {
                        "title": result.get("title"),
                        "url": result.get("url"),
                        "content": result.get("content"),
                    }
                )

            return {
                "query": query,
                "results": results,
                "sources": format_web_sources(results),
            }

        except requests.exceptions.RequestException as e:
            last_error = e

        except Exception as e:
            last_error = e

        if attempt < 2:
            time.sleep(1.5 * (attempt + 1))

    print(f"Tavily search failed: {last_error}")

    return {
        "query": query,
        "results": [],
        "sources": [],
        "error": (
            "Live web search is temporarily unavailable. "
            "Please try again later."
        ),
    }


# ============================================================
# 18. QUESTION ROUTING
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
    "this week",
    "what changed",
    "latest update",
    "latest updates",
    "current update",
    "current updates",
    "current version",
    "latest version",
    "recent developments",
    "new developments",
    "new release",
    "new releases",
    "released recently",
    "as of",
]


PAPER_TERMS = [
    "paper",
    "research paper",
    "uploaded paper",
    "according to the paper",
    "according to my paper",
    "from the paper",
    "in the paper",
    "paper architecture",
    "paper methodology",
    "paper experiment",
    "paper results",
    "paper findings",
    "architecture",
    "methodology",
    "experiment",
    "experiments",
    "results",
    "findings",
    "proposed",
    "according to",
    "gru",
    "bert",
    "rag",
    "attention",
    "self-attention",
    "multi-head attention",
    "multi head attention",
    "transformer",
    "transformers",
    "react",
    "few shot",
    "few-shot",
    "encoder",
    "decoder",
]


def is_time_sensitive(question):
    question_lower = question.lower()

    return any(
        term in question_lower
        for term in TIME_SENSITIVE_TERMS
    )


def is_paper_question(question):
    question_lower = question.lower()

    return any(
        term in question_lower
        for term in PAPER_TERMS
    )


def routing_decision(question):
    """
    Deterministic application-level router.

    This is intentionally separate from the LLM. The LLM must not
    be allowed to bypass RAG for known paper concepts or bypass
    live web search for time-sensitive questions.
    """

    paper = is_paper_question(question)
    web = is_time_sensitive(question)

    if paper and web:
        return "both"

    if paper:
        return "paper"

    if web:
        return "web"

    return "agent"


# ============================================================
# 19. CONTENT HELPERS
# ============================================================

def extract_text(content):
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        text_parts = []

        for block in content:
            if not isinstance(block, dict):
                continue

            text = block.get("text")

            if isinstance(text, str):
                text_parts.append(text)

        return "".join(text_parts)

    return str(content)


def parse_tool_result(content):
    """
    Convert ToolMessage content into a Python dictionary.

    Supports:
    - dict
    - Python dictionary string
    - JSON dictionary string
    """

    if isinstance(content, dict):
        return content

    if isinstance(content, str):
        try:
            result = ast.literal_eval(content)

            if isinstance(result, dict):
                return result

        except (ValueError, SyntaxError):
            pass

        try:
            result = json.loads(content)

            if isinstance(result, dict):
                return result

        except (ValueError, TypeError, json.JSONDecodeError):
            pass

    return {}


# ============================================================
# 20. FORMAT AGENT RESULT
# ============================================================

def format_agent_result(result):
    messages = result.get("messages", [])

    sources = []
    tools_used = []

    final_message = None

    for message in reversed(messages):
        if isinstance(message, AIMessage):
            if not getattr(message, "tool_calls", None):
                final_message = message
                break

    if final_message is None and messages:
        final_message = messages[-1]

    answer = ""

    if final_message is not None:
        answer = extract_text(
            final_message.content
        )

    for message in messages:
        if not isinstance(message, ToolMessage):
            continue

        tool_name = getattr(
            message,
            "name",
            None,
        )

        if tool_name and tool_name not in tools_used:
            tools_used.append(tool_name)

        tool_result = parse_tool_result(
            message.content
        )

        if not isinstance(tool_result, dict):
            continue

        if tool_name == "research_papers":
            for source in tool_result.get("sources", []):
                formatted_source = {
                    "type": "paper",
                    "source": source,
                }

                if formatted_source not in sources:
                    sources.append(formatted_source)

        elif tool_name == "web_search":
            for source in tool_result.get("sources", []):
                formatted_source = {
                    "type": "web",
                    "source": source,
                }

                if formatted_source not in sources:
                    sources.append(formatted_source)

    return {
        "answer": answer,
        "sources": sources,
        "tools_used": tools_used,
    }


# ============================================================
# 21. SYNTHESIS PROMPTS
# ============================================================

WEB_SYNTHESIS_PROMPT = ChatPromptTemplate.from_template(
    """
You are a research assistant answering a current-information question.

The user asked:
{question}

Use ONLY the live web-search evidence below for claims about
current/latest/recent information.

Rules:
- Do not invent facts.
- Do not use your internal knowledge to fill missing current facts.
- Prefer the most recent information in the supplied results.
- Clearly distinguish dates when useful.
- If the supplied results do not support an important claim, say so.
- Answer directly and clearly.
- Do not mention the internal implementation.

LIVE WEB EVIDENCE:
{evidence}

Answer:
"""
)


COMBINED_SYNTHESIS_PROMPT = ChatPromptTemplate.from_template(
    """
You are a research assistant.

The user asked:
{question}

You have TWO evidence sources.

SOURCE A — UPLOADED RESEARCH PAPERS:
{paper_evidence}

SOURCE B — LIVE WEB:
{web_evidence}

Rules:
- Use the uploaded-paper evidence for claims about the user's papers.
- Use live-web evidence for current/latest/recent claims.
- Do not invent facts.
- Do not silently replace paper evidence with general knowledge.
- Clearly distinguish paper findings from current web information.
- If one evidence source does not contain enough information, say so.
- Give a clear, useful answer.
- Do not mention the internal implementation.

Answer:
"""
)


# ============================================================
# 22. DETERMINISTIC ROUTER HELPERS
# ============================================================

def make_tool_message(tool_name, tool_result):
    """
    Create a ToolMessage so the existing Streamlit/source
    formatting pipeline can process deterministic routes exactly
    like LangGraph tool calls.
    """

    return ToolMessage(
        content=json.dumps(
            tool_result,
            ensure_ascii=False,
        ),
        name=tool_name,
        tool_call_id=f"router_{tool_name}",
    )


def run_paper_route(question):
    tool_result = research_papers.invoke(
        {
            "question": question,
        }
    )

    answer = tool_result.get(
        "answer",
        "",
    )

    return {
        "messages": [
            HumanMessage(content=question),
            make_tool_message(
                "research_papers",
                tool_result,
            ),
            AIMessage(content=answer),
        ]
    }


def run_web_route(question):
    tool_result = web_search.invoke(
        {
            "query": question,
        }
    )

    if tool_result.get("error"):
        answer = (
            "I couldn't verify the current information because "
            "the live web search is temporarily unavailable."
        )
    elif not tool_result.get("results"):
        answer = (
            "I couldn't verify the current information because "
            "the live web search returned no usable results."
        )
    else:
        evidence = "\n\n".join(
            (
                f"TITLE: {item.get('title', '')}\n"
                f"URL: {item.get('url', '')}\n"
                f"CONTENT: {item.get('content', '')}"
            )
            for item in tool_result.get("results", [])
        )

        messages = WEB_SYNTHESIS_PROMPT.invoke(
            {
                "question": question,
                "evidence": evidence,
            }
        )

        answer = extract_text(
            llm.invoke(messages).content
        )

    return {
        "messages": [
            HumanMessage(content=question),
            make_tool_message(
                "web_search",
                tool_result,
            ),
            AIMessage(content=answer),
        ]
    }


def run_combined_route(question):
    paper_result = research_papers.invoke(
        {
            "question": question,
        }
    )

    web_result = web_search.invoke(
        {
            "query": question,
        }
    )

    paper_evidence = (
        paper_result.get("answer", "")
        + "\n\n"
        + paper_result.get("source_text", "")
    )

    web_evidence = "\n\n".join(
        (
            f"TITLE: {item.get('title', '')}\n"
            f"URL: {item.get('url', '')}\n"
            f"CONTENT: {item.get('content', '')}"
        )
        for item in web_result.get("results", [])
    )

    if web_result.get("error"):
        web_evidence = (
            "Live web search failed. Do not invent current information."
        )

    messages = COMBINED_SYNTHESIS_PROMPT.invoke(
        {
            "question": question,
            "paper_evidence": paper_evidence,
            "web_evidence": web_evidence,
        }
    )

    answer = extract_text(
        llm.invoke(messages).content
    )

    return {
        "messages": [
            HumanMessage(content=question),
            make_tool_message(
                "research_papers",
                paper_result,
            ),
            make_tool_message(
                "web_search",
                web_result,
            ),
            AIMessage(content=answer),
        ]
    }


# ============================================================
# 23. LANGGRAPH AGENT FOR GENERAL QUESTIONS
# ============================================================

@st.cache_resource
def load_general_agent():
    print("Creating general research agent...")

    return create_agent(
        model=llm,
        tools=[
            research_papers,
            web_search,
        ],
        system_prompt="""
You are a research assistant that provides accurate,
evidence-based answers.

The application has already routed paper-specific and
time-sensitive questions before reaching you.

For general questions:
- Answer clearly and accurately.
- Do not claim that information is current/latest unless
  live web evidence is available.
- If you decide a tool is genuinely useful, use it.
- When tools are used, base factual claims on their results.
- Do not invent sources, dates, versions, statistics, or facts.
- Do not mention internal routing or implementation details.
""",
    )


general_agent = load_general_agent()


# ============================================================
# 24. PUBLIC RESEARCH AGENT
# ============================================================

class DeterministicResearchAgent:
    """
    Public interface used by app.py.

    app.py can continue doing:

        research_agent.invoke({...})

    but the application now decides the evidence route BEFORE
    the LLM gets to answer.

    Routes:
        paper -> RAG
        web   -> Tavily
        both  -> RAG + Tavily
        agent -> LangGraph agent
    """

    def invoke(self, input_data, config=None, **kwargs):
        messages = input_data.get(
            "messages",
            [],
        )

        question = ""

        if messages:
            last_message = messages[-1]

            if isinstance(last_message, dict):
                question = last_message.get(
                    "content",
                    "",
                )
            else:
                question = getattr(
                    last_message,
                    "content",
                    "",
                )

        question = str(question).strip()

        route = routing_decision(question)

        print(
            f"Routing question to: {route}"
        )

        if route == "paper":
            return run_paper_route(question)

        if route == "web":
            return run_web_route(question)

        if route == "both":
            return run_combined_route(question)

        # General question: let LangGraph handle it.
        return general_agent.invoke(
            input_data,
            config=config,
            **kwargs,
        )


research_agent = DeterministicResearchAgent()