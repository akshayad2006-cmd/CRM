# =========================================
# 1. IMPORTS
# =========================================
import re
import urllib
import pandas as pd
import hashlib
import os
import uuid

from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import create_engine, text

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document

from langgraph.graph import StateGraph, END
from typing import TypedDict, Optional, List, Dict, Any

from langchain_groq import ChatGroq


# =========================================
# 2. MEMORY STORE
# =========================================
conversation_memory = []

# =========================================
# USER AUTH + ROLE ACCESS
# =========================================

USERS = {
    "admin": {
        "password": "admin123",
        "role": "admin",
        "name": "Admin User"
    },

    "salesmgr1": {
        "password": "salesmgr123",
        "role": "sales_manager",
        "name": "Sales Manager"
    },

    "jim.h": {
        "password": "jim123",
        "role": "sales_executive",
        "name": "Jim Halpert"
    },

    "support1": {
        "password": "support123",
        "role": "support_executive",
        "name": "Support Executive"
    }
}

SESSIONS = {}

ROLE_TABLES = {
    "admin": [
        "UserRole",
        "Users",
        "AuditLogs",
        "Campaigns",
        "Customers",
        "Employees",
        "Products",
        "Leads",
        "Sales",
        "Opportunities",
        "SalesPipeline",
        "Quotes",
        "Orders",
        "OrderItems",
        "Invoices",
        "Payments",
        "CustomerInteractions",
        "SupportTickets",
        "CustomerFeedback"
    ],

    "sales_manager": [
        "Campaigns",
        "Customers",
        "Employees",
        "Products",
        "Leads",
        "Sales",
        "Opportunities",
        "SalesPipeline",
        "Quotes",
        "Orders",
        "OrderItems",
        "Invoices",
        "Payments",
        "CustomerInteractions",
        "CustomerFeedback"
    ],

    "sales_executive": [
        "Campaigns",
        "Customers",
        "Products",
        "Leads",
        "Sales",
        "Opportunities",
        "SalesPipeline",
        "Quotes",
        "Orders",
        "OrderItems",
        "CustomerInteractions",
        "CustomerFeedback"
    ],

    "support_executive": [
        "Customers",
        "Products",
        "Orders",
        "OrderItems",
        "CustomerInteractions",
        "SupportTickets",
        "CustomerFeedback"
    ]
}

# =========================================
# 3. LLM SETUP
# =========================================
from dotenv import load_dotenv
import os

load_dotenv()

llm = ChatGroq(
    groq_api_key=os.getenv("GROQ_API_KEY"),
    model="openai/gpt-oss-120b",
    temperature=0
)


# =========================================
# 4. SQL SERVER CONNECTION
# =========================================
server = "localhost,1433"
database = "crm"
username = "sa"
password = "StrongPass@123"

conn_str = (
    f"DRIVER={{ODBC Driver 18 for SQL Server}};"
    f"SERVER={server};"
    f"DATABASE={database};"
    f"UID={username};"
    f"PWD={password};"
    "Encrypt=no;"
    "TrustServerCertificate=yes;"
)

params = urllib.parse.quote_plus(conn_str)

engine = create_engine(
    f"mssql+pyodbc:///?odbc_connect={params}",
    fast_executemany=True
)


# =========================================
# 5. EMBEDDINGS
# =========================================
# =========================================
# 6. LOAD DATABASE SCHEMA + FOREIGN KEYS
# =========================================

CHROMA_DIR = "./chroma_db"

def get_schema_text():

    columns_query = """
    SELECT
        TABLE_NAME,
        COLUMN_NAME,
        DATA_TYPE,
        ORDINAL_POSITION
    FROM INFORMATION_SCHEMA.COLUMNS
    ORDER BY TABLE_NAME, ORDINAL_POSITION
    """

    fk_query = """
    SELECT
        OBJECT_NAME(f.parent_object_id) AS ParentTable,
        COL_NAME(fc.parent_object_id,fc.parent_column_id) AS ParentColumn,
        OBJECT_NAME(f.referenced_object_id) AS RefTable,
        COL_NAME(fc.referenced_object_id,fc.referenced_column_id) AS RefColumn
    FROM sys.foreign_keys f
    INNER JOIN sys.foreign_key_columns fc
        ON f.object_id = fc.constraint_object_id
    """

    cols_df = pd.read_sql(columns_query, engine)
    fk_df = pd.read_sql(fk_query, engine)

    docs = []

    for table in cols_df["TABLE_NAME"].unique():

        table_df = cols_df[
            cols_df["TABLE_NAME"] == table
        ]

        cols = "\n".join([
            f"- {r.COLUMN_NAME} ({r.DATA_TYPE})"
            for _, r in table_df.iterrows()
        ])

        fk_text = ""

        table_fk = fk_df[
            (fk_df["ParentTable"] == table)
            | (fk_df["RefTable"] == table)
        ]

        if len(table_fk) > 0:

            fk_text = "\nFOREIGN KEYS:\n"

            for _, fk in table_fk.iterrows():

                fk_text += (
                    f"{fk.ParentTable}.{fk.ParentColumn}"
                    f" -> "
                    f"{fk.RefTable}.{fk.RefColumn}\n"
                )

        docs.append(
            Document(
                page_content=f"""
TABLE NAME:
{table}

COLUMNS:
{cols}

{fk_text}

DATABASE:
Microsoft SQL Server
"""
            )
        )

    return docs

# =========================================
# EMBEDDINGS
# =========================================
from langchain_huggingface import HuggingFaceEmbeddings

embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

##used to auto embedding
def build_or_load_chroma():

    docs = get_schema_text()

    schema_hash = hashlib.md5(
        "".join([d.page_content for d in docs]).encode()
    ).hexdigest()

    hash_file = os.path.join(
        CHROMA_DIR,
        "schema_hash.txt"
    )

    rebuild = True

    if os.path.exists(hash_file):

        old_hash = open(
            hash_file,
            "r"
        ).read()

        if old_hash == schema_hash:
            rebuild = False

    if rebuild:

        if os.path.exists(CHROMA_DIR):
            import shutil
            shutil.rmtree(CHROMA_DIR)

        vectordb = Chroma.from_documents(
            documents=docs,
            embedding=embeddings,
            persist_directory=CHROMA_DIR,
            collection_name="sqlserver_schema"
        )

        with open(hash_file, "w") as f:
            f.write(schema_hash)

    else:

        vectordb = Chroma(
            persist_directory=CHROMA_DIR,
            embedding_function=embeddings,
            collection_name="sqlserver_schema"
        )

    return vectordb


schema_index = build_or_load_chroma()

# =========================================
# 7. RETRIEVE RELEVANT SCHEMA
# =========================================
def extract_table_name(schema_text):
    match = re.search(
        r"TABLE NAME:\s*([^\n\r]+)",
        schema_text,
        re.IGNORECASE
    )

    if not match:
        return ""

    return match.group(1).strip()

def retrieve_schema(question, role):
    allowed_tables = ROLE_TABLES.get(role, [])

    allowed_tables_lower = {
        table.lower()
        for table in allowed_tables
    }

    docs = schema_index.similarity_search(
        question,
        k=20
    )

    allowed_docs = []

    for doc in docs:
        table_name = extract_table_name(doc.page_content)

        if table_name.lower() in allowed_tables_lower:
            allowed_docs.append(doc.page_content)

    if not allowed_docs:
        return """
No allowed schema found for this user role.

If the question needs restricted tables, return:

SELECT 'Access denied or information not available for your role' AS Message
"""

    return "\n".join(allowed_docs)
# =========================================
# 8. GREETING / GENERAL CHAT
# =========================================
def is_general_chat(question):

    q = question.lower().strip()

    greetings = {
        "hi",
        "hello",
        "hey",
        "good morning",
        "good evening",
        "who are you",
        "what can you do"
    }

    return q in greetings


def general_chat_response(question):

    q = question.lower()

    if "how are you" in q:
        return "I am doing great. I can help you generate SQL queries from your SQL Server database."

    if "who are you" in q:
        return "I am an AI SQL Assistant powered by FastAPI, LangGraph, Groq LLM, and SQL Server."

    if "what can you do" in q:
        return "I can understand natural language questions and generate SQL queries for your SQL Server database."

    return "Hello! Ask me anything about your SQL Server database."

# =========================================
# 9. CLEAN SQL
# =========================================
def clean_sql(response):

    response = re.sub(r"```sql", "", response, flags=re.IGNORECASE)
    response = re.sub(r"```", "", response)

    return response.strip()


# =========================================
# 10. SQL GENERATOR
# =========================================
def sql_agent(question, role):

    schema = retrieve_schema(question, role)

    memory_context = "\n".join(
        conversation_memory[-5:]
    )

    prompt = f"""
You are a Senior SQL Server Database Expert.

Generate ONLY Microsoft SQL Server T-SQL.

Current user role:
{role}

STRICT RULES:

1. Return SQL only.
2. No explanation.
3. No markdown.
4. Use only tables in schema.
5. Use only columns in schema.
6. Never invent table names.
7. Never invent column names.
8. Use joins using foreign keys.
9. Use TOP instead of LIMIT.
10. Use SELECT queries only.
11. Never generate:
DELETE
UPDATE
DROP
ALTER
TRUNCATE
MERGE
EXEC

12. If schema does not contain required information or the user asks for restricted information, return:

SELECT 'Access denied or information not available for your role' AS Message

Conversation History:
{memory_context}

Relevant Schema:
{schema}

Question:
{question}
"""

    response = llm.invoke(prompt).content

    return clean_sql(response)


def extract_tables_from_sql(query):
    matches = re.findall(
        r"\b(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_\.\[\]]*)",
        query,
        re.IGNORECASE
    )

    tables = []

    for item in matches:
        table = item.split(".")[-1]
        table = table.replace("[", "").replace("]", "")
        tables.append(table.lower())

    return tables


def is_safe_sql(query, role):

    blocked = [
        "DELETE",
        "UPDATE",
        "DROP",
        "ALTER",
        "TRUNCATE",
        "MERGE",
        "EXEC",
        "EXECUTE",
        "INSERT",
        "CREATE"
    ]

    sql_upper = query.upper().strip()

    if not sql_upper.startswith("SELECT"):
        return False, "Only SELECT queries are allowed."

    for word in blocked:
        pattern = r"\b" + word + r"\b"

        if re.search(pattern, sql_upper):
            return False, f"Unsafe SQL blocked: {word}"

    allowed_tables = ROLE_TABLES.get(role, [])

    allowed_tables_lower = {
        table.lower()
        for table in allowed_tables
    }

    used_tables = extract_tables_from_sql(query)

    for table in used_tables:
        if table not in allowed_tables_lower:
            return False, f"Access denied. Your role cannot access table: {table}"

    return True, None
# =========================================
# 11. VALIDATE SQL
# =========================================
def validate_sql(query):

    try:

        with engine.connect() as conn:

            conn.execute(text("SET PARSEONLY ON"))
            conn.execute(text(query))
            conn.execute(text("SET PARSEONLY OFF"))

        return True, None

    except Exception as e:

        return False, str(e)


# =========================================
# 12. EXECUTE SQL
# =========================================
def execute_sql(query):

    try:

        df = pd.read_sql(query, engine)

        return {
            "data": df.to_dict(orient="records"),
            "error": None
        }

    except Exception as e:

        return {
            "data": [],
            "error": str(e)
        }


# =========================================
# 13. SUMMARIZER
# =========================================
def summarize_agent(result, error):

    if error:
        return error

    if not result:
        return "No data found."

    prompt = f"""
You are a CRM analytics assistant.

Answer using ONLY the query result.

Query Result:

{result[:20]}

Provide concise business answer.
"""

    return llm.invoke(prompt).content


# =========================================
# 14. LANGGRAPH STATE
# =========================================
class State(TypedDict):

    question: str
    role: str
    sql: str
    valid: bool
    error: Optional[str]
    result: List[Dict[str, Any]]
    answer: Any
    general_chat: bool

# =========================================
# 15. GENERAL CHAT NODE
# =========================================
def node_intent(state):

    question = state["question"]

    if is_general_chat(question):

        return {
            "general_chat": True,
            "answer": general_chat_response(question)
        }

    return {
        "general_chat": False
    }


# =========================================
# 16. SQL NODE
# =========================================
def node_sql(state):

    if state["general_chat"]:
        return {
            "sql": "",
            "valid": True,
            "error": None
        }

    role = state["role"]

    sql = sql_agent(
        state["question"],
        role
    )

    safe, error = is_safe_sql(
        sql,
        role
    )

    if not safe:
        return {
            "sql": sql,
            "valid": False,
            "error": error
        }

    valid, error = validate_sql(sql)

    return {
        "sql": sql,
        "valid": valid,
        "error": error
    }


# =========================================
# 17. EXECUTE NODE
# =========================================
def node_execute(state):

    if state["general_chat"]:

        return {
            "result": []
        }

    if not state["valid"]:

        return {
            "result": [],
            "error": state["error"]
        }

    output = execute_sql(state["sql"])

    return {
        "result": output["data"],
        "error": output["error"]
    }


# =========================================
# 18. SUMMARY NODE
# =========================================
def node_summary(state):

    if state["general_chat"]:

        return {
            "answer": state["answer"]
        }

    return {
        "answer": summarize_agent(
            state["result"],
            state["error"]
        )
    }


# =========================================
# 19. BUILD GRAPH
# =========================================
graph = StateGraph(State)

graph.add_node("intent", node_intent)
graph.add_node("sql", node_sql)
graph.add_node("execute", node_execute)
graph.add_node("summary", node_summary)

graph.set_entry_point("intent")

graph.add_edge("intent", "sql")
graph.add_edge("sql", "execute")
graph.add_edge("execute", "summary")
graph.add_edge("summary", END)

app_graph = graph.compile()
# =========================================
# FUNCTION TO CHECK LOGGED-IN USER
# =========================================
def get_current_user(authorization: Optional[str]):
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Login required"
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header"
        )

    token = authorization.replace("Bearer ", "").strip()

    user = SESSIONS.get(token)

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Session expired. Please login again."
        )

    return user


# =========================================
# 20. FASTAPI
# =========================================
app = FastAPI()

app.mount("/static", StaticFiles(directory="./"), name="static")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================
# 21. REQUEST MODEL
# =========================================
class LoginRequest(BaseModel):
    username: str
    password: str


class ChatRequest(BaseModel):
    question: str


# =========================================
# 22. HOME PAGE
# =========================================
@app.get("/", response_class=HTMLResponse)
async def home():

    with open("index_final.html", "r", encoding="utf-8") as f:
        return f.read()

# =========================================
# LOGIN API
# =========================================
@app.post("/login")
def login_api(request: LoginRequest):
    user = USERS.get(request.username)

    if not user or user["password"] != request.password:
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )

    token = str(uuid.uuid4())

    SESSIONS[token] = {
        "username": request.username,
        "role": user["role"],
        "name": user["name"]
    }

    return {
        "message": "Login successful",
        "token": token,
        "username": request.username,
        "role": user["role"],
        "name": user["name"]
    }

# =========================================
# 23. CHAT API
# =========================================
@app.post("/ask")
def ask_api(
    request: ChatRequest,
    authorization: Optional[str] = Header(None)
):

    user = get_current_user(authorization)

    question = request.question
    role = user["role"]

    result = app_graph.invoke({
        "question": question,
        "role": role
    })

    data = result.get("result", [])

    columns = []

    if len(data) > 0:
        columns = list(data[0].keys())

    conversation_memory.append(
        f"""
User: {user["username"]}
Role: {role}
Question: {question}
SQL: {result.get('sql')}
Answer: {result.get('answer')}
"""
    )

    conversation_memory[:] = conversation_memory[-10:]

    return {
        "question": question,
        "user": user["username"],
        "role": role,
        "sql": result.get("sql"),
        "answer": result.get("answer"),
        "data": data,
        "columns": columns,
        "error": result.get("error")
    }


# =========================================
# 24. CLEAR MEMORY API
# =========================================
@app.post("/clear-memory")
def clear_memory():

    global conversation_memory

    conversation_memory = []

    return {
        "message": "Memory cleared successfully"
    }


# =========================================
# 25. RUN SERVER
# =========================================
if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000
    )