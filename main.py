import os
import json
import sqlite3
import pypdf
from datetime import datetime, timedelta
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, File, UploadFile
from pydantic import BaseModel
from groq import Groq
from google import genai
# Load environment variables from .env
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

app = FastAPI(title="Flap Backend API")

def init_db():
    conn = sqlite3.connect("flashcards.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS decks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        )
    ''')
    # Added ease_factor, interval, and repetitions to track study history
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            deck_id INTEGER,
            front TEXT NOT NULL,
            back TEXT NOT NULL,
            next_review_date TEXT,
            ease_factor REAL DEFAULT 2.5,
            interval INTEGER DEFAULT 0,
            repetitions INTEGER DEFAULT 0,
            FOREIGN KEY (deck_id) REFERENCES decks(id)
        )
    ''')
    # Create quizzes table for storing generated quiz questions
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS quizzes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            deck_id INTEGER,
            question TEXT NOT NULL,
            options TEXT NOT NULL,  -- JSON array of options
            correct_answer INTEGER,  -- Index of correct option (0-3)
            explanation TEXT,
            FOREIGN KEY (deck_id) REFERENCES decks(id)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

class ReviewUpdate(BaseModel):
    quality: int  # 3 = Hard, 4 = Good, 5 = Easy

@app.post("/cards/{card_id}/review")
async def review_card(card_id: int, review: ReviewUpdate):
    conn = sqlite3.connect("flashcards.db")
    cursor = conn.cursor()
    cursor.execute("SELECT ease_factor, interval, repetitions FROM cards WHERE id = ?", (card_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Card not found")

    ease_factor, interval, repetitions = row
    q = review.quality

    if q < 3:
        repetitions = 0
        interval = 1
    else:
        if repetitions == 0:
            interval = 1
        elif repetitions == 1:
            interval = 6
        else:
            interval = round(interval * ease_factor)
        repetitions += 1

    ease_factor = ease_factor + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
    ease_factor = max(1.3, ease_factor)

    next_review_date = (datetime.now() + timedelta(days=interval)).isoformat()

    cursor.execute("""
        UPDATE cards
        SET next_review_date = ?, ease_factor = ?, interval = ?, repetitions = ?
        WHERE id = ?
    """, (next_review_date, ease_factor, interval, repetitions, card_id))

    conn.commit()
    conn.close()
    return {"message": "Card updated", "next_review": next_review_date}

@app.get("/decks/{deck_id}/due")
async def get_due_cards(deck_id: int):
    conn = sqlite3.connect("flashcards.db")
    cursor = conn.cursor()
    now_iso = datetime.now().isoformat()

    cursor.execute("""
        SELECT id, front, back FROM cards
        WHERE deck_id = ? AND (next_review_date IS NULL OR next_review_date <= ?)
    """, (deck_id, now_iso))

    cards = [{"id": row[0], "front": row[1], "back": row[2]} for row in cursor.fetchall()]
    conn.close()
    return {"due_cards": cards}

@app.post("/upload/")
async def upload_pdf(file: UploadFile = File(...), count: int = 15):
    file_location = f"temp_{file.filename}"
    try:
        with open(file_location, "wb") as f:
            f.write(await file.read())

        extracted_text = ""
        reader = pypdf.PdfReader(file_location)
        for page in reader.pages:
            text = page.extract_text()
            if text:
                extracted_text += text + "\n"
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF extraction error: {e}")
    finally:
        if os.path.exists(file_location):
            os.remove(file_location)

    if not extracted_text.strip():
        raise HTTPException(status_code=400, detail="Could not extract text from PDF")

    base_prompt = f"""
    Extract highly detailed, granular flashcards from the following text.
    DO NOT summarize or group distinct concepts together.
    Create exactly {count} flashcards (or as many as the text supports if it's too short).
    Generate an individual card for every key term, specific definition, and distinct process found in the text.

    Return ONLY a valid JSON array of objects. Each object must have exactly two keys: 'front' and 'back'. Do not include markdown code blocks like ```json.

    Text:
    {extracted_text}
    """

    cards_data = []

    # PRIMARY ENGINE: Gemini -> FALLBACK: Groq
    try:
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not set in .env")

        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        response = gemini_client.models.generate_content(
            model='gemini-3.6-flash',
            contents=base_prompt
        )
        raw_json = response.text.replace('```json', '').replace('```', '').strip()
        cards_data = json.loads(raw_json)
        print("Successfully generated cards via Gemini!")

    except Exception as e:
        print(f"Gemini failed: {e}. Routing to Groq fallback...")
        try:
            if not GROQ_API_KEY:
                raise ValueError("GROQ_API_KEY is not set in .env")

            groq_client = Groq(api_key=GROQ_API_KEY)
            chat_completion = groq_client.chat.completions.create(
                messages=[{"role": "user", "content": base_prompt}],
                model="groq/compound",
                temperature=0.3
            )
            raw_json = chat_completion.choices[0].message.content.replace('```json', '').replace('```', '').strip()
            cards_data = json.loads(raw_json)
            print("Successfully generated cards via Groq!")
        except Exception as groq_err:
            raise HTTPException(status_code=500, detail=f"Both AI engines failed. Groq error: {groq_err}")

    if not isinstance(cards_data, list):
        raise HTTPException(status_code=500, detail="AI did not return a valid array.")

    # Save to Database
    conn = sqlite3.connect("flashcards.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO decks (name) VALUES (?)", (file.filename,))
    deck_id = cursor.lastrowid

    for card in cards_data:
        front = card.get("front", "No Front")
        back = card.get("back", "No Back")
        cursor.execute("INSERT INTO cards (deck_id, front, back) VALUES (?, ?, ?)", (deck_id, front, back))

    conn.commit()
    conn.close()

    return {"message": "Upload successful", "deck_id": deck_id, "cards_generated": len(cards_data)}

@app.get("/decks/")
async def get_decks():
    conn = sqlite3.connect("flashcards.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM decks")
    decks = [{"id": row[0], "name": row[1]} for row in cursor.fetchall()]
    conn.close()
    return {"decks": decks}

@app.get("/decks/{deck_id}/cards")
async def get_cards(deck_id: int):
    conn = sqlite3.connect("flashcards.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, front, back FROM cards WHERE deck_id = ?", (deck_id,))
    cards = [{"id": row[0], "front": row[1], "back": row[2]} for row in cursor.fetchall()]
    conn.close()
    return {"cards": cards}

@app.delete("/decks/{deck_id}")
async def delete_deck(deck_id: int):
    conn = sqlite3.connect("flashcards.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM decks WHERE id = ?", (deck_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Deck not found")

    cursor.execute("DELETE FROM cards WHERE deck_id = ?", (deck_id,))
    cursor.execute("DELETE FROM decks WHERE id = ?", (deck_id,))
    conn.commit()
    conn.close()
    return {"message": "Deck deleted successfully."}

# NEW ENDPOINT: GET /decks/{deck_id}/quizzes
@app.get("/decks/{deck_id}/quizzes")
async def get_quizzes(deck_id: int):
    conn = sqlite3.connect("flashcards.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, question, options, correct_answer, explanation FROM quizzes WHERE deck_id = ?", (deck_id,))
    quizzes = []
    for row in cursor.fetchall():
        # row: (id, question, options_json, correct_answer, explanation)
        options = json.loads(row[2]) if row[2] else []
        quizzes.append({
            "id": row[0],
            "question": row[1],
            "options": options,
            "correct_answer": row[3],
            "explanation": row[4]
        })
    conn.close()
    return {"quizzes": quizzes}


@app.post("/decks/{deck_id}/generate-quiz")
async def generate_quiz(deck_id: int, count: int = 5):
    # Verify deck exists
    conn = sqlite3.connect("flashcards.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM decks WHERE id = ?", (deck_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Deck not found")

    # Fetch cards for this deck
    cursor.execute("SELECT id, front, back FROM cards WHERE deck_id = ?", (deck_id,))
    cards = [{"id": row[0], "front": row[1], "back": row[2]} for row in cursor.fetchall()]
    conn.close()

    if not cards:
        raise HTTPException(status_code=400, detail="No cards found in deck")

    # Prepare text for quiz generation
    text_content = "\n\n".join([
        f"Card {i+1}:\nFront: {card['front']}\nBack: {card['back']}"
        for i, card in enumerate(cards[:20])  # Limit to first 20 cards to avoid too much text
    ])

    # Limit count to available cards
    count = min(count, len(cards))

    base_prompt = f"""
    Based on the following flashcards, generate {count} multiple-choice quiz questions.
    Each question should have 4 options (A, B, C, D) with one correct answer.
    For each question, also provide a brief explanation of why the correct answer is correct.

    Return ONLY a valid JSON array of objects. Each object must have exactly these keys:
    - 'question': the quiz question text
    - 'options': a JSON array of exactly 4 strings [optionA, optionB, optionC, optionD]
    - 'correct_answer': an integer (0, 1, 2, or 3) indicating the index of the correct option
    - 'explanation': a brief explanation of why the correct answer is correct

    Do not include markdown code blocks like ```json.

    Flashcards:
    {text_content}
    """

    quizzes_data = []

    # Try Gemini first, then Groq as fallback
    try:
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not set in .env")

        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        response = gemini_client.models.generate_content(
            model='gemini-3.6-flash',
            contents=base_prompt
        )
        raw_json = response.text.replace('```json', '').replace('```', '').strip()
        quizzes_data = json.loads(raw_json)
        print(f"Successfully generated {len(quizzes_data)} quiz questions via Gemini!")

    except Exception as e:
        print(f"Gemini failed: {e}. Routing to Groq fallback...")
        try:
            if not GROQ_API_KEY:
                raise ValueError("GROQ_API_KEY is not set in .env")

            groq_client = Groq(api_key=GROQ_API_KEY)
            chat_completion = groq_client.chat.completions.create(
                messages=[{"role": "user", "content": base_prompt}],
                model="groq/compound",
                temperature=0.3
            )
            raw_json = chat_completion.choices[0].message.content.replace('```json', '').replace('```', '').strip()
            quizzes_data = json.loads(raw_json)
            print(f"Successfully generated {len(quizzes_data)} quiz questions via Groq!")

        except Exception as groq_err:
            raise HTTPException(status_code=500, detail=f"Both AI engines failed. Groq error: {groq_err}")

    # Validate the generated data
    if not isinstance(quizzes_data, list):
        raise HTTPException(status_code=500, detail="AI did not return a valid array.")

    # Save quizzes to database
    conn = sqlite3.connect("flashcards.db")
    cursor = conn.cursor()

    # Clear previously generated quizzes for this deck so they don't accumulate
    cursor.execute("DELETE FROM quizzes WHERE deck_id = ?", (deck_id,))

    saved_count = 0
    for quiz in quizzes_data[:count]:  # Ensure we don't save more than requested
        if not isinstance(quiz, dict):
            continue

        question = quiz.get("question", "").strip()
        options = quiz.get("options", [])
        correct_answer = quiz.get("correct_answer", 0)
        explanation = quiz.get("explanation", "").strip()

        # Validate required fields
        if not question or not isinstance(options, list) or len(options) != 4:
            continue

        # Ensure correct_answer is valid
        if not isinstance(correct_answer, int) or correct_answer < 0 or correct_answer > 3:
            correct_answer = 0  # Default to first option if invalid

        # Save to database
        cursor.execute(
            "INSERT INTO quizzes (deck_id, question, options, correct_answer, explanation) VALUES (?, ?, ?, ?, ?)",
            (deck_id, question, json.dumps(options), correct_answer, explanation)
        )
        saved_count += 1

    conn.commit()
    conn.close()

    if saved_count == 0:
        raise HTTPException(status_code=500, detail="Failed to generate valid quiz questions")

    return {"message": f"Generated {saved_count} quiz questions successfully", "count": saved_count}