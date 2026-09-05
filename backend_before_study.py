"""
Course Content Simplification Agent
Flask Backend + IBM watsonx.ai

Model:
    mistralai/mistral-small-3-1-24b-instruct-2503

Features:
    - Paste course content
    - Upload and extract text from PDF
    - Beginner / Intermediate / Advanced explanations
    - Grounded educational simplification
    - Core academic concept identification
    - Key concepts
    - Real-world analogy

Run:
    python backend.py
"""

import os
import re
import requests

from pypdf import PdfReader
from flask import Flask, request, jsonify
from flask_cors import CORS


# ============================================================
# Flask configuration
# ============================================================

app = Flask(__name__)
CORS(app)

# Maximum uploaded file size: 10 MB
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024


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
    Build a grounded, concept-focused learning prompt.
    """

    guidance = {
        "beginner": (
            "Use simple words, short sentences, and everyday language. "
            "Assume the learner has little prior knowledge. "
            "Explain necessary technical terms in simple language."
        ),

        "intermediate": (
            "Use clear educational language with moderate technical detail. "
            "Assume the learner understands basic terminology. "
            "Explain important technical terms briefly."
        ),

        "advanced": (
            "Use precise technical language and preserve important "
            "technical depth, relationships, mechanisms, limitations, "
            "and nuances."
        ),
    }

    subject_text = ""

    if subject:
        subject_text = f"""
SUBJECT AREA:
{subject}
"""

    return f"""
You are an expert academic teaching assistant.

Your job is to transform the provided course material into a clear,
accurate explanation for a student at the requested learning level.

The goal is to make the educational material easier to understand
WITHOUT changing its technical meaning.

STUDENT LEARNING LEVEL:
{level}

{subject_text}

LEARNING LEVEL GUIDANCE:
{guidance[level]}

============================================================
SOURCE COURSE CONTENT
============================================================

{content}

============================================================
MOST IMPORTANT RULE — IDENTIFY THE CORE CONCEPT
============================================================

First identify the MAIN ACADEMIC CONCEPT being taught.

The explanation must focus primarily on that academic concept.

Course material may contain:
- project descriptions
- background stories
- application scenarios
- project goals
- testing information
- implementation details
- examples
- input/output data
- unrelated contextual information

Do NOT automatically treat these as academic concepts.

For example:

If the material discusses Merge Sort in the context of route
costs, the main academic concept is Merge Sort.

Explain:
- what Merge Sort is
- how Merge Sort works
- how the algorithm divides and combines data
- important properties supported by the source

Do NOT make "military missions" or "route costs" the central
concept unless the material specifically teaches those concepts.

Project context should only be included when it genuinely helps
the student understand the academic concept.

============================================================
GROUNDING RULES
============================================================

1. Use the provided course material as the primary source.

2. Do not invent facts.

3. Do not invent applications or use cases.

4. Do not invent relationships between concepts.

5. Do not turn project-specific details into academic concepts.

6. Do not make a minor example the main explanation.

7. Preserve important definitions, algorithms, formulas, steps,
   terminology, and relationships from the source.

8. Simplify the wording without changing the technical meaning.

9. If information is missing or unclear, do not guess.

10. Focus on what a student actually needs to learn.

11. Do not unnecessarily repeat:
    - project goals
    - testing results
    - input sizes
    - implementation details
    - unrelated background information

12. If the source contains both an academic concept and a
    project/application context, prioritize the academic concept.

13. Do not claim that a concept is used for a particular purpose
    unless that purpose is explicitly supported by the source.

14. Examples and analogies must accurately represent the academic
    concept.

============================================================
LEARNING-LEVEL RULES
============================================================

BEGINNER:

- Use simple everyday language.
- Use short and clear sentences.
- Avoid unnecessary jargon.
- Explain technical terms when first introduced.
- Break complicated ideas into small steps.
- Use one simple analogy.

INTERMEDIATE:

- Use moderate technical vocabulary.
- Assume basic familiarity.
- Explain important terminology briefly.
- Include useful relationships between concepts.
- Provide enough technical detail to support understanding.

ADVANCED:

- Use precise technical terminology.
- Preserve technical depth.
- Explain mechanisms and relationships.
- Include important limitations and nuances when supported
  by the source.
- Avoid oversimplifying technical details.

============================================================
OUTPUT FORMAT
============================================================

Return EXACTLY these three sections:

SIMPLIFIED EXPLANATION:

Write 3–5 clear paragraphs.

Paragraph 1:
Give a simple definition of the MAIN ACADEMIC CONCEPT.

Paragraph 2:
Explain how the concept works.

Paragraph 3:
Explain important properties, steps, or relationships.

Additional paragraph:
Include only information that is genuinely useful for learning
the concept and is supported by the source.

KEY CONCEPTS:

- Concept 1: short explanation
- Concept 2: short explanation
- Concept 3: short explanation

Only include genuine academic concepts.

Do not include project-specific details unless they are themselves
important academic concepts.

ANALOGY:

Give one simple analogy that accurately represents the MAIN
ACADEMIC CONCEPT.

The analogy must help the student understand the concept.

Do not create an analogy that introduces unsupported technical
claims.

If an accurate analogy cannot be created, write:

N/A

============================================================
FORMATTING RULES
============================================================

- Use plain text only.
- Do NOT use Markdown bold.
- Do NOT use **.
- Do NOT use HTML.
- Do NOT use tables.
- Do NOT add extra sections.
- Do NOT add a conclusion.
- Do NOT include meta-commentary.
- Do NOT mention these instructions.
- Do NOT say "according to the prompt".
- Do NOT repeat the source word-for-word.

Your response must contain ONLY:

SIMPLIFIED EXPLANATION:
KEY CONCEPTS:
ANALOGY:
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
            "temperature": 0.2,
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
    # Parse response
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
# Clean model formatting
# ============================================================

def clean_text(text):
    """
    Remove accidental Markdown formatting generated by the model.
    """

    if not text:
        return ""

    text = text.replace("**", "")
    text = text.replace("__", "")

    # Remove Markdown heading markers
    text = re.sub(
        r"^\s*#{1,6}\s*",
        "",
        text,
        flags=re.MULTILINE
    )

    # Normalize bullet characters
    text = text.replace("•", "-")

    # Normalize excessive blank lines
    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text
    )

    return text.strip()


# ============================================================
# Parse structured model response
# ============================================================

def parse_response(raw_text):

    raw_text = raw_text.strip()

    simplified = ""
    key_concepts = ""
    analogy = None

    # --------------------------------------------------------
    # Locate sections
    # --------------------------------------------------------

    explanation_marker = "SIMPLIFIED EXPLANATION:"
    concepts_marker = "KEY CONCEPTS:"
    analogy_marker = "ANALOGY:"

    if explanation_marker in raw_text:

        after_explanation = raw_text.split(
            explanation_marker,
            1
        )[1]

        if concepts_marker in after_explanation:

            simplified = after_explanation.split(
                concepts_marker,
                1
            )[0].strip()

            after_concepts = after_explanation.split(
                concepts_marker,
                1
            )[1]

            if analogy_marker in after_concepts:

                key_concepts = after_concepts.split(
                    analogy_marker,
                    1
                )[0].strip()

                analogy_text = after_concepts.split(
                    analogy_marker,
                    1
                )[1].strip()

                if (
                    analogy_text
                    and analogy_text.upper() != "N/A"
                ):
                    analogy = analogy_text

            else:

                key_concepts = after_concepts.strip()

        else:

            simplified = after_explanation.strip()

    else:

        # Fallback if model ignored section formatting
        simplified = raw_text

    # --------------------------------------------------------
    # Clean accidental formatting
    # --------------------------------------------------------

    simplified = clean_text(simplified)
    key_concepts = clean_text(key_concepts)

    if analogy:
        analogy = clean_text(analogy)

    # --------------------------------------------------------
    # Fallback values
    # --------------------------------------------------------

    if not simplified:

        simplified = clean_text(raw_text)

    if not key_concepts:

        key_concepts = (
            "- Review the simplified explanation above."
        )

    return {
        "simplified_explanation": simplified,
        "key_concepts": key_concepts,
        "analogy": analogy,
    }


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
        # Validate course content
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
# POST /api/extract-pdf
# ============================================================

@app.route("/api/extract-pdf", methods=["POST"])
def extract_pdf():

    try:

        # ----------------------------------------------------
        # Check file
        # ----------------------------------------------------

        if "file" not in request.files:

            return jsonify({
                "error":
                    "No PDF file was uploaded."
            }), 400

        file = request.files["file"]

        if not file or not file.filename:

            return jsonify({
                "error":
                    "Please select a PDF file."
            }), 400

        # ----------------------------------------------------
        # Validate extension
        # ----------------------------------------------------

        filename = file.filename.lower()

        if not filename.endswith(".pdf"):

            return jsonify({
                "error":
                    "Only PDF files are supported."
            }), 400

        # ----------------------------------------------------
        # Read PDF
        # ----------------------------------------------------

        reader = PdfReader(file)

        page_text = []

        for page in reader.pages:

            try:

                text = page.extract_text() or ""

            except Exception:

                text = ""

            if text.strip():

                page_text.append(
                    text.strip()
                )

        # ----------------------------------------------------
        # Combine text
        # ----------------------------------------------------

        extracted_text = "\n\n".join(
            page_text
        ).strip()

        # ----------------------------------------------------
        # Check extracted content
        # ----------------------------------------------------

        if not extracted_text:

            return jsonify({
                "error":
                    "No readable text was found in this PDF. "
                    "The PDF may be scanned or image-only."
            }), 400

        return jsonify({
            "success": True,
            "filename": file.filename,
            "pages": len(reader.pages),
            "text": extracted_text,
        })

    except Exception as e:

        print()
        print(
            "PDF EXTRACTION ERROR:",
            str(e)
        )
        print()

        return jsonify({
            "error":
                f"Could not extract PDF text: {str(e)}"
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
        "pdf_support": True,
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
    print("PDF      :", "Enabled")
    print("Server   :", "http://localhost:5000")
    print("=" * 70)
    print()

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )