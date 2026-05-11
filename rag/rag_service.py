import re
from pathlib import Path
from typing import List

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

from model.init_llm import deepseekllm, qwenembedding
from utils.loader_prompt import load_prompt

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
FAISS_DIR = Path(__file__).parent / "faiss"


# ── Prompt ─────────────────────────────────────────────────────────────────────


prompt = ChatPromptTemplate.from_template(
    load_prompt("rag.txt")
)

deepseek_model = deepseekllm
embedding = qwenembedding


# ── Document loaders with document-structure-aware chunking ───────────────────

def _load_qa_docs(path: Path, source_name: str) -> List[Document]:
    """Q&A files: one chunk per numbered Q&A pair, prefixed with category."""
    text = path.read_text(encoding="utf-8")
    docs: List[Document] = []
    current_category = ""
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        # Category header  ### xxx
        if line.startswith("###"):
            current_category = line.lstrip("#").strip()
            i += 1
            continue
        # Skip other headers
        if line.startswith("#"):
            i += 1
            continue
        # Numbered bold question:  1. **question?**
        m = re.match(r"^\d+\.\s+\*\*(.+?)\*\*\s*$", line)
        if m:
            question = m.group(1)
            answer_parts: List[str] = []
            i += 1
            while i < len(lines):
                nxt = lines[i].strip()
                if nxt.startswith("- "):
                    answer_parts.append(nxt[2:].strip())
                    i += 1
                elif re.match(r"^\d+\.\s+\*\*", nxt) or nxt.startswith("#"):
                    break
                elif nxt == "":
                    i += 1
                else:
                    answer_parts.append(nxt)
                    i += 1
            content = f"【{current_category}】\n问：{question}\n答：{''.join(answer_parts)}"
            docs.append(Document(page_content=content,
                                 metadata={"source": source_name, "category": current_category}))
        else:
            i += 1
    return docs


def _load_fault_docs(path: Path) -> List[Document]:
    """Fault file: one chunk per numbered fault entry (故障现象/检测/修复)."""
    docs: List[Document] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if re.match(r"^\d+\.\s+故障现象：", line):
            docs.append(Document(page_content=line,
                                 metadata={"source": "故障排除", "type": "fault"}))
    return docs


def _load_section_list_docs(path: Path, source_name: str) -> List[Document]:
    """Maintenance / buying-guide files: one chunk per numbered item, prefixed with section."""
    docs: List[Document] = []
    current_section = ""
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("##"):
            current_section = stripped.lstrip("#").strip()
            continue
        if stripped.startswith("#"):
            continue
        m = re.match(r"^\d+\.\s+(.+)", stripped)
        if m:
            prefix = f"【{current_section}】" if current_section else ""
            docs.append(Document(page_content=f"{prefix}{m.group(1)}",
                                 metadata={"source": source_name, "section": current_section}))
    return docs


def _load_pdf_docs(path: Path) -> List[Document]:
    """PDF: load pages then split with RecursiveCharacterTextSplitter."""
    try:
        from langchain_community.document_loaders import PyPDFLoader
    except ImportError:
        print(f"[WARN] PyPDFLoader unavailable, skipping {path.name}")
        return []
    pages = PyPDFLoader(str(path)).load()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=400,
        chunk_overlap=40,
        separators=["\n\n", "\n", "。", "；", "，", " ", ""],
    )
    return splitter.split_documents(pages)


# ── Index build / load ─────────────────────────────────────────────────────────

def _collect_all_docs() -> List[Document]:
    all_docs: List[Document] = []

    for fname in ("扫地机器人100问2.txt", "扫拖一体机器人100问.txt"):
        p = DATA_DIR / fname
        if p.exists():
            docs = _load_qa_docs(p, fname.replace(".txt", ""))
            all_docs.extend(docs)
            print(f"  {fname}: {len(docs)} chunks")

    fault_path = DATA_DIR / "故障排除.txt"
    if fault_path.exists():
        docs = _load_fault_docs(fault_path)
        all_docs.extend(docs)
        print(f"  故障排除.txt: {len(docs)} chunks")

    for fname in ("维护保养.txt", "选购指南.txt"):
        p = DATA_DIR / fname
        if p.exists():
            docs = _load_section_list_docs(p, fname.replace(".txt", ""))
            all_docs.extend(docs)
            print(f"  {fname}: {len(docs)} chunks")

    pdf_path = DATA_DIR / "扫地机器人100问.pdf"
    if pdf_path.exists():
        docs = _load_pdf_docs(pdf_path)
        all_docs.extend(docs)
        print(f"  扫地机器人100问.pdf: {len(docs)} chunks")

    return all_docs


def build_vectorstore(force: bool = False) -> FAISS:
    """Build FAISS index from all knowledge-base documents and persist it."""
    index_file = FAISS_DIR / "index.faiss"
    if index_file.exists() and not force:
        print("FAISS index already exists. Use build_vectorstore(force=True) to rebuild.")
        return load_vectorstore()

    print("Building FAISS index...")
    all_docs = _collect_all_docs()
    print(f"Total chunks: {len(all_docs)}")

    vectorstore = FAISS.from_documents(all_docs, embedding)
    FAISS_DIR.mkdir(parents=True, exist_ok=True)
    vectorstore.save_local(str(FAISS_DIR))
    print(f"Index saved to {FAISS_DIR}")
    return vectorstore


def load_vectorstore() -> FAISS:
    """Load persisted FAISS index, building it first if absent."""
    index_file = FAISS_DIR / "index.faiss"
    if not index_file.exists():
        return build_vectorstore()
    return FAISS.load_local(str(FAISS_DIR), embedding,
                            allow_dangerous_deserialization=True)


# ── RAG chain ──────────────────────────────────────────────────────────────────

def build_rag_chain(vectorstore: FAISS):
    """
    Retrieval strategy:
    - MMR (Maximum Marginal Relevance) to balance relevance and diversity
    - fetch_k=20 candidates, return k=5 after MMR re-ranking
    - lambda_mult=0.7 leans toward relevance over diversity
    """
    retriever = vectorstore.as_retriever(
        search_type="mmr",
        search_kwargs={"k": 5, "fetch_k": 20, "lambda_mult": 0.7},
    )

    def format_docs(docs: List[Document]) -> str:
        return "\n\n---\n\n".join(d.page_content for d in docs)

    chain = (
        {"context": retriever | format_docs, "input": RunnablePassthrough()}
        | prompt
        | deepseek_model
        | StrOutputParser()
    )
    return chain


def stream_answer(chain, question: str) -> str:
    """Stream the answer token by token, returning the full text when done."""
    full = []
    for chunk in chain.stream(question):
        print(chunk, end="", flush=True)
        full.append(chunk)
    print()
    return "".join(full)


# ── Test ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    vs = load_vectorstore()
    chain = build_rag_chain(vs)

    test_questions = [
        "扫地机器人主刷多久需要更换一次？",
        "机器人找不到充电座怎么处理？",
        "拖地后地面有水渍怎么办？",
        "如何选购适合宠物家庭的扫地机器人？",
        "机器人出现滴滴滴报警声是什么原因？",
        "水箱漏水怎么修复？",
    ]

    for q in test_questions:
        print(f"\n{'=' * 60}")
        print(f"问题：{q}")
        print("回答：", end="")
        stream_answer(chain, q)
