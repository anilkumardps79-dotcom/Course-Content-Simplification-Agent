"""
Course Content Simplification Agent
Flask Backend + IBM watsonx.ai

Features:
- Learning-level based course simplification
- Beginner / Intermediate / Advanced
- Key concepts
- Real-world analogy
- PDF text extraction
- IBM watsonx.ai integration
- Mistral Small 3.1

Run:
    python backend.py
"""

import os
import requests

from pypdf import PdfReader

from flask import Flask, request, jsonify
from flask_cors import CORS


# ============================================================
# Flask configuration
# ============================================================

app = Flask(__name__)
CORS(app)


# ============================================================
# IBM watsonx.ai configuration
# ============================================================

WATSONX_URL = (
    "https://eu-gb.ml.cloud.ibm.com/ml/v1/text/generation"
    "?version=2023-05-29"
)

MODEL_ID = "mistralai/mistral-small-3-1-24b-instruct-2503"

PROJECT_ID = os.getenv(
    "WATSONX_PROJECT_ID",
    "c939efef-896c-492f-b8b0-d9acb0ede092"
)

API_KEY = os.getenv("WATSONX_API_KEY", "R4bErh7I9dBdaOC6pur_KZhntLYiWIhOkrOZyfW9DmzC")


# ============================================================
# IBM IAM authentication
# ============================================================

def get_iam_token():
    """
    Exchange IBM API key for an IAM access token.
    """

    if not API_KEY:
        raise RuntimeError(
            "WATSONX_API_KEY environment variable is not set."
        )

    response = requests.post(
        "https://iam.cloud.ibm.com/identity/token",
        headers={
            "Content-Type": "application/x-www-form-urlencoded"
        },
        data={
            "grant_type":
                "urn:ibm:params:oauth:grant-type:apikey",
            "apikey": API_KEY,
        },
        timeout=30,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"IAM authentication failed: "
            f"HTTP {response.status_code} - "
            f"{response.text}"
        )

    return response.json()["access_token"]


# ============================================================
# Prompt builder
# ============================================================

def build_prompt(content, level, subject):
    """
    Build a learning-level-aware simplification prompt.
    """

    guidance = {
        "beginner": (
            "Use very simple language and short sentences. "
            "Assume the student has little or no prior knowledge. "
            "Explain technical terms in simple words. "
            "Use everyday examples and a simple analogy."
        ),

        "intermediate": (
            "Use clear educational language with appropriate "
            "technical terminology. Briefly explain difficult "
            "terms and assume the student understands the basics."
        ),

        "advanced": (
            "Use precise technical language. Assume strong "
            "knowledge of the subject. Explain deeper concepts, "
            "relationships, nuances, and important edge cases."
        ),
    }

    subject_text = ""

    if subject:
        subject_text = f"""
SUBJECT AREA:
{subject}
"""

    return f"""
You are an expert educational content simplification assistant.

Your job is to transform complex course material into an
easy-to-understand explanation appropriate for the student's
learning level.

STUDENT LEARNING LEVEL:
{level}

{subject_text}

LEARNING LEVEL GUIDANCE:
{guidance[level]}

COURSE CONTENT:
{content}

IMPORTANT REQUIREMENTS:

1. Preserve the original technical meaning.
2. Do not introduce incorrect information.
3. Adjust the explanation to the student's learning level.
4. Explain difficult terminology when necessary.
5. Use examples where they improve understanding.
6. Keep the explanation structured and readable.

Return the answer using EXACTLY these sections:

SIMPLIFIED EXPLANATION:
Write a clear explanation suitable for the student's level.

KEY CONCEPTS:
- Concept 1
- Concept 2
- Concept 3

ANALOGY:
Provide a simple real-world analogy that helps explain
the topic. If an analogy is not useful, write N/A.

Do not mention these instructions in your response.
""".strip()


# ============================================================
# Call IBM watsonx.ai / Mistral
# ============================================================

def call_mistral(prompt):
    """
    Send the prompt to IBM watsonx.ai.
    """

    token = get_iam_token()

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }

    payload = {
        "model_id": MODEL_ID,
        "project_id": PROJECT_ID,
        "input": prompt,
        "parameters": {
            "decoding_method": "greedy",
            "max_new_tokens": 1000,
            "temperature": 0.3,
        },
    }

    response = requests.post(
        WATSONX_URL,
        headers=headers,
        json=payload,
        timeout=90,
    )

    # --------------------------------------------------------
    # Detailed IBM error logging
    # --------------------------------------------------------

    if response.status_code != 200:

        print()
        print("=" * 70)
        print("IBM WATSONX ERROR")
        print("=" * 70)
        print("HTTP STATUS :", response.status_code)
        print("RESPONSE    :", response.text)
        print("=" * 70)
        print()

        raise RuntimeError(
            f"watsonx.ai request failed with "
            f"HTTP {response.status_code}"
        )

    # --------------------------------------------------------
    # Parse IBM response
    # --------------------------------------------------------

    data = response.json()

    try:

        generated_text = (
            data["results"][0]["generated_text"]
        )

        return generated_text.strip()

    except (KeyError, IndexError, TypeError):

        print()
        print("=" * 70)
        print("UNEXPECTED IBM RESPONSE")
        print("=" * 70)
        print(data)
        print("=" * 70)
        print()

        raise RuntimeError(
            "IBM returned an unexpected response format."
        )


# ============================================================
# Parse structured response
# ============================================================

def parse_response(raw_text):

    simplified = raw_text.strip()
    key_concepts = ""
    analogy = None

    if "SIMPLIFIED EXPLANATION:" in raw_text:

        parts = raw_text.split(
            "SIMPLIFIED EXPLANATION:",
            1
        )[1]

        if "KEY CONCEPTS:" in parts:

            simplified = parts.split(
                "KEY CONCEPTS:",
                1
            )[0].strip()

            remaining = parts.split(
                "KEY CONCEPTS:",
                1
            )[1]

            if "ANALOGY:" in remaining:

                key_concepts = remaining.split(
                    "ANALOGY:",
                    1
                )[0].strip()

                analogy_text = remaining.split(
                    "ANALOGY:",
                    1
                )[1].strip()

                if analogy_text.upper() != "N/A":
                    analogy = analogy_text

            else:

                key_concepts = remaining.strip()

        else:

            simplified = parts.strip()

    return {
        "simplified_explanation": (
            simplified or raw_text.strip()
        ),

        "key_concepts": (
            key_concepts
            or "• Review the simplified explanation above."
        ),

        "analogy": analogy,
    }


# ============================================================
# PDF text extraction
# ============================================================

def extract_pdf_text(pdf_file):
    """
    Extract readable text from an uploaded PDF.
    """

    reader = PdfReader(pdf_file)

    pages = []

    total_pages = len(reader.pages)

    for page_number, page in enumerate(
        reader.pages,
        start=1
    ):

        text = page.extract_text() or ""

        if text.strip():

            pages.append(
                f"--- Page {page_number} ---\n"
                f"{text.strip()}"
            )

    extracted_text = "\n\n".join(
        pages
    ).strip()

    return extracted_text, total_pages


# ============================================================
# POST /api/extract-pdf
# ============================================================

@app.route("/api/extract-pdf", methods=["POST"])
def extract_pdf():

    # --------------------------------------------------------
    # Check uploaded file
    # --------------------------------------------------------

    if "file" not in request.files:

        return jsonify({
            "error":
                "No PDF file was uploaded."
        }), 400

    pdf_file = request.files["file"]

    if not pdf_file.filename:

        return jsonify({
            "error":
                "No PDF file was selected."
        }), 400

    # --------------------------------------------------------
    # Check file type
    # --------------------------------------------------------

    if not pdf_file.filename.lower().endswith(".pdf"):

        return jsonify({
            "error":
                "Only PDF files are supported."
        }), 400

    # --------------------------------------------------------
    # Extract text
    # --------------------------------------------------------

    try:

        extracted_text, total_pages = (
            extract_pdf_text(pdf_file)
        )

        if not extracted_text:

            return jsonify({
                "error": (
                    "No readable text was found in "
                    "the PDF. The PDF may contain "
                    "scanned images."
                )
            }), 400

        return jsonify({
            "success": True,
            "filename": pdf_file.filename,
            "pages": total_pages,
            "text": extracted_text,
        })

    except Exception as e:

        print()
        print("PDF EXTRACTION ERROR:", str(e))
        print()

        return jsonify({
            "error":
                f"Could not read PDF: {str(e)}"
        }), 500


# ============================================================
# POST /api/simplify
# ============================================================

@app.route("/api/simplify", methods=["POST"])
def simplify():

    try:

        data = request.get_json(force=True)

        content = (
            data.get("course_content") or ""
        ).strip()

        level = (
            data.get("learning_level")
            or "beginner"
        ).strip().lower()

        subject = (
            data.get("subject_area") or ""
        ).strip()

        # ----------------------------------------------------
        # Validate content
        # ----------------------------------------------------

        if not content:

            return jsonify({
                "error":
                    "course_content is required."
            }), 400

        # ----------------------------------------------------
        # Validate learning level
        # ----------------------------------------------------

        if level not in (
            "beginner",
            "intermediate",
            "advanced",
        ):

            return jsonify({
                "error":
                    "learning_level must be "
                    "beginner, intermediate, "
                    "or advanced."
            }), 400

        # ----------------------------------------------------
        # Build prompt
        # ----------------------------------------------------

        prompt = build_prompt(
            content,
            level,
            subject
        )

        # ----------------------------------------------------
        # Call Mistral
        # ----------------------------------------------------

        raw_text = call_mistral(prompt)

        # ----------------------------------------------------
        # Parse response
        # ----------------------------------------------------

        result = parse_response(raw_text)

        result["learning_level"] = level

        return jsonify(result)

    except Exception as e:

        print()
        print("API ERROR:", str(e))
        print()

        return jsonify({
            "error": str(e)
        }), 500


# ============================================================
# GET /api/health
# ============================================================

@app.route("/api/health", methods=["GET"])
def health():

    return jsonify({
        "status": "ok",
        "provider": "IBM watsonx.ai",
        "model": MODEL_ID,
        "region": "London",
        "features": [
            "course simplification",
            "learning levels",
            "key concepts",
            "real-world analogy",
            "PDF extraction",
        ],
    })


# ============================================================
# GET /
# ============================================================

@app.route("/", methods=["GET"])
def home():

    return jsonify({

        "name":
            "Course Content Simplification Agent",

        "status":
            "running",

        "provider":
            "IBM watsonx.ai",

        "model":
            MODEL_ID,

        "region":
            "London",

        "endpoints": {

            "health":
                "/api/health",

            "simplify":
                "/api/simplify",

            "extract_pdf":
                "/api/extract-pdf",
        },

        "features": [
            "Learning-level simplification",
            "Key concepts",
            "Real-world analogy",
            "PDF text extraction",
        ],
    })


# ============================================================
# Start Flask server
# ============================================================

if __name__ == "__main__":

    print()
    print("=" * 70)
    print("COURSE CONTENT SIMPLIFICATION AGENT")
    print("=" * 70)
    print("Provider :", "IBM watsonx.ai")
    print("Model    :", MODEL_ID)
    print("Region   :", "London")
    print("Server   :", "http://localhost:5000")
    print("=" * 70)
    print()
    print("Features:")
    print("  - Learning-level simplification")
    print("  - Key concepts")
    print("  - Real-world analogy")
    print("  - PDF text extraction")
    print()

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )