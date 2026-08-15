import streamlit as st
import sqlite3
import json
from pathlib import Path
from datetime import datetime
import httpx


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Research Agent",
    page_icon="🧠",
    layout="wide"
)


# ============================================================
# DATABASE CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

DB_PATH = BASE_DIR / "research_history.db"


# ============================================================
# DATABASE FUNCTIONS
# ============================================================

def get_connection():
    """
    Create SQLite database connection.
    """

    return sqlite3.connect(
        DB_PATH,
        check_same_thread=False
    )


def initialize_database():
    """
    Create search history table if it does not exist.
    """

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS search_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            sources TEXT,
            tools_used TEXT,
            created_at TEXT NOT NULL
        )
        """
    )

    conn.commit()

    conn.close()


def save_search(
    question,
    answer,
    sources,
    tools_used
):
    """
    Save a completed research search permanently.
    """

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO search_history
        (
            question,
            answer,
            sources,
            tools_used,
            created_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            question,
            answer,
            json.dumps(sources),
            json.dumps(tools_used),
            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        )
    )

    conn.commit()

    search_id = cursor.lastrowid

    conn.close()

    return search_id


def get_search_history():
    """
    Return all searches, newest first.
    """

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            id,
            question,
            answer,
            sources,
            tools_used,
            created_at
        FROM search_history
        ORDER BY id DESC
        """
    )

    rows = cursor.fetchall()

    conn.close()

    history = []

    for row in rows:

        history.append(
            {
                "id": row[0],
                "question": row[1],
                "answer": row[2],
                "sources": json.loads(row[3])
                if row[3]
                else [],
                "tools_used": json.loads(row[4])
                if row[4]
                else [],
                "created_at": row[5]
            }
        )

    return history


def get_search(search_id):
    """
    Get one search by database ID.
    """

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            id,
            question,
            answer,
            sources,
            tools_used,
            created_at
        FROM search_history
        WHERE id = ?
        """,
        (search_id,)
    )

    row = cursor.fetchone()

    conn.close()

    if row is None:
        return None

    return {
        "id": row[0],
        "question": row[1],
        "answer": row[2],
        "sources": json.loads(row[3])
        if row[3]
        else [],
        "tools_used": json.loads(row[4])
        if row[4]
        else [],
        "created_at": row[5]
    }


def delete_search(search_id):
    """
    Delete one search from history.
    """

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute(
        """
        DELETE FROM search_history
        WHERE id = ?
        """,
        (search_id,)
    )

    conn.commit()

    conn.close()


def clear_history():
    """
    Delete all search history.
    """

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute(
        """
        DELETE FROM search_history
        """
    )

    conn.commit()

    conn.close()


# ============================================================
# INITIALIZE DATABASE
# ============================================================

initialize_database()


# ============================================================
# SESSION STATE
# ============================================================

if "selected_search_id" not in st.session_state:

    st.session_state.selected_search_id = None


# ============================================================
# SOURCE CARDS
# ============================================================

def display_sources(sources):
    """
    Display paper and web sources as professional cards.
    """

    if not sources:
        return


    st.divider()

    st.subheader("📚 Sources")


    # ========================================================
    # SEPARATE PAPER AND WEB SOURCES
    # ========================================================

    paper_sources = [
        source
        for source in sources
        if source.get("type") == "paper"
    ]


    web_sources = [
        source
        for source in sources
        if source.get("type") == "web"
    ]


    # ========================================================
    # PAPER SOURCES
    # ========================================================

    if paper_sources:

        st.markdown("### 📄 Research Papers")


        for index, source in enumerate(
            paper_sources,
            start=1
        ):

            source_data = source.get(
                "source",
                "Unknown source"
            )


            st.markdown(
                f"""
                <div style="
                    border: 1px solid rgba(128,128,128,0.25);
                    border-radius: 12px;
                    padding: 14px 16px;
                    margin-bottom: 10px;
                    background-color: rgba(128,128,128,0.06);
                ">

                    <div style="
                        font-size: 16px;
                        font-weight: 600;
                    ">
                        📄 {source_data}
                    </div>

                    <div style="
                        font-size: 13px;
                        opacity: 0.65;
                        margin-top: 5px;
                    ">
                        Research Paper Source #{index}
                    </div>

                </div>
                """,
                unsafe_allow_html=True
            )


    # ========================================================
    # WEB SOURCES
    # ========================================================

    if web_sources:

        st.markdown("### 🌐 Web Sources")


        for index, source in enumerate(
            web_sources,
            start=1
        ):

            source_data = source.get(
                "source",
                {}
            )


            title = source_data.get(
                "title",
                "Web Source"
            )


            url = source_data.get(
                "url",
                ""
            )


            if url:

                st.markdown(
                    f"""
                    <div style="
                        border: 1px solid rgba(128,128,128,0.25);
                        border-radius: 12px;
                        padding: 14px 16px;
                        margin-bottom: 10px;
                        background-color: rgba(128,128,128,0.06);
                    ">

                        <div style="
                            font-size: 16px;
                            font-weight: 600;
                        ">
                            🌐 {title}
                        </div>

                        <div style="
                            font-size: 13px;
                            opacity: 0.65;
                            margin-top: 5px;
                        ">
                            Live Web Source #{index}
                        </div>

                        <div style="
                            margin-top: 8px;
                        ">
                            <a
                                href="{url}"
                                target="_blank"
                                style="
                                    text-decoration: none;
                                "
                            >
                                🔗 Open Source ↗
                            </a>
                        </div>

                    </div>
                    """,
                    unsafe_allow_html=True
                )

            else:

                st.markdown(
                    f"""
                    <div style="
                        border: 1px solid rgba(128,128,128,0.25);
                        border-radius: 12px;
                        padding: 14px 16px;
                        margin-bottom: 10px;
                        background-color: rgba(128,128,128,0.06);
                    ">

                        <div style="
                            font-size: 16px;
                            font-weight: 600;
                        ">
                            🌐 {title}
                        </div>

                        <div style="
                            font-size: 13px;
                            opacity: 0.65;
                            margin-top: 5px;
                        ">
                            Live Web Source #{index}
                        </div>

                    </div>
                    """,
                    unsafe_allow_html=True
                )


# ============================================================
# DISPLAY RESULT
# ============================================================

def display_sources(sources):
    """
    Display paper and web sources using native Streamlit components.
    """

    if not sources:
        return

    st.divider()
    st.subheader("📚 Sources")

    # Separate sources
    paper_sources = [
        source
        for source in sources
        if source.get("type") == "paper"
    ]

    web_sources = [
        source
        for source in sources
        if source.get("type") == "web"
    ]

    # --------------------------------------------------------
    # RESEARCH PAPERS
    # --------------------------------------------------------

    if paper_sources:

        st.markdown("### 📄 Research Papers")

        for index, source in enumerate(
            paper_sources,
            start=1
        ):

            source_data = source.get(
                "source",
                "Unknown source"
            )

            st.markdown(
                f"**{index}. 📄 {source_data}**"
            )

    # --------------------------------------------------------
    # WEB SOURCES
    # --------------------------------------------------------

    if web_sources:

        st.markdown("### 🌐 Web Sources")

        for index, source in enumerate(
            web_sources,
            start=1
        ):

            source_data = source.get(
                "source",
                {}
            )

            # Safety check
            if not isinstance(source_data, dict):
                st.write(
                    f"{index}. 🌐 {source_data}"
                )
                continue

            title = source_data.get(
                "title",
                "Web Source"
            )

            url = source_data.get(
                "url",
                ""
            )

            # Display clean source title
            st.markdown(
                f"**{index}. 🌐 {title}**"
            )

            # Display URL as a proper Streamlit link
            if url:

                st.link_button(
                    "🔗 Open Source",
                    url
                )

            st.divider()


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.title(
        "🧠 Research Agent"
    )

    st.caption(
        "Your AI research workspace"
    )


    # ========================================================
    # NEW RESEARCH
    # ========================================================

    if st.button(
        "➕ New Research",
        use_container_width=True
    ):

        st.session_state.selected_search_id = None

        st.rerun()


    st.divider()


    # ========================================================
    # SEARCH HISTORY
    # ========================================================

    st.subheader(
        "🕘 Search History"
    )


    history = get_search_history()


    if not history:

        st.caption(
            "No searches yet."
        )


    else:

        for item in history:

            search_id = item["id"]

            question_text = item["question"]


            # ------------------------------------------------
            # SHORT QUESTION
            # ------------------------------------------------

            if len(question_text) > 42:

                button_text = (
                    question_text[:42]
                    + "..."
                )

            else:

                button_text = question_text


            # ------------------------------------------------
            # HISTORY ITEM
            # ------------------------------------------------

            col1, col2 = st.columns(
                [5, 1]
            )


            with col1:

                if st.button(
                    f"🔍 {button_text}",
                    key=f"search_{search_id}",
                    use_container_width=True
                ):

                    st.session_state.selected_search_id = (
                        search_id
                    )

                    st.rerun()


            with col2:

                if st.button(
                    "✕",
                    key=f"delete_{search_id}"
                ):

                    delete_search(
                        search_id
                    )


                    if (
                        st.session_state.selected_search_id
                        == search_id
                    ):

                        st.session_state.selected_search_id = None


                    st.rerun()


    # ========================================================
    # CLEAR HISTORY
    # ========================================================

    if history:

        st.divider()


        if st.button(
            "🗑️ Clear History",
            use_container_width=True
        ):

            clear_history()

            st.session_state.selected_search_id = None

            st.rerun()


# ============================================================
# MAIN PAGE
# ============================================================

st.title(
    "🧠 Research Agent"
)


st.write(
    "Ask questions about research papers or search the live web."
)


# ============================================================
# CHAT INPUT
# ============================================================

question = st.chat_input(
    "Ask a research question..."
)


# ============================================================
# NEW QUESTION
# ============================================================

if question:

    # ========================================================
    # IMPORT BACKEND ONLY WHEN QUESTION IS ASKED
    # ========================================================

    from rag.main import (
        research_agent,
        format_agent_result
    )


    # ========================================================
    # USER QUESTION
    # ========================================================

    with st.chat_message("user"):

        st.write(question)


    # ========================================================
    # RUN RESEARCH AGENT
    # ========================================================

    with st.chat_message("assistant"):

        with st.spinner(
            "🔬 Researching..."
        ):

            # ------------------------------------------------
            # CHECK MISTRAL API KEY
            # ------------------------------------------------

            import os

            if not os.getenv("MISTRAL_API_KEY"):

                st.error(
                    "❌ MISTRAL_API_KEY is not configured "
                    "in Streamlit Cloud Secrets."
                )

                st.stop()


            # ------------------------------------------------
            # RUN RESEARCH AGENT SAFELY
            # ------------------------------------------------

            try:

                result = research_agent.invoke(
                    {
                        "messages": [
                            {
                                "role": "user",
                                "content": question
                            }
                        ]
                    }
                )

            except httpx.HTTPStatusError as e:

                status_code = e.response.status_code

                st.error(
                    f"❌ Mistral API returned HTTP {status_code}"
                )

                if status_code == 401:

                    st.warning(
                        "The Mistral API key is invalid, "
                        "expired, or is not being read correctly."
                    )

                elif status_code == 402:

                    st.warning(
                        "The Mistral account requires billing/payment "
                        "or has no available API usage."
                    )

                elif status_code == 403:

                    st.warning(
                        "The API key does not have permission "
                        "for this request or model."
                    )

                elif status_code == 404:

                    st.warning(
                        "The requested Mistral model or endpoint "
                        "was not found."
                    )

                elif status_code == 422:

                    st.warning(
                        "Mistral rejected the request. "
                        "The model name or request parameters "
                        "may be invalid."
                    )

                elif status_code == 429:

                    st.warning(
                        "Mistral rate limit reached. "
                        "Please wait and try again."
                    )

                else:

                    st.warning(
                        "Mistral returned an unexpected API error."
                    )

                st.stop()


            clean_result = format_agent_result(
                result
            )


            answer = clean_result["answer"]

            sources = clean_result["sources"]

            tools_used = clean_result["tools_used"]


        # ====================================================
        # ANSWER
        # ====================================================

        st.markdown(answer)


        # ====================================================
        # TOOLS
        # ====================================================

        if tools_used:

            st.divider()

            st.subheader(
                "🛠️ Tools Used"
            )


            for tool in tools_used:

                if tool == "research_papers":

                    st.write(
                        "📄 Research Papers"
                    )

                elif tool == "web_search":

                    st.write(
                        "🌐 Web Search"
                    )

                else:

                    st.write(
                        f"🔧 {tool}"
                    )


# -----------------------------------------------
# SOURCES
# -----------------------------------------------

        display_sources(
            sources
        )


# ============================================================
# DISPLAY SELECTED HISTORY ITEM
# ============================================================

elif (
    st.session_state.selected_search_id
    is not None
):

    selected_search = get_search(
        st.session_state.selected_search_id
    )


    if selected_search:

        st.divider()

        display_result(
            selected_search
        )