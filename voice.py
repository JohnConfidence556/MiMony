import os

from dotenv import load_dotenv
from groq import Groq

load_dotenv()
client = Groq()

STT_MODEL = os.getenv("STT_MODEL", "whisper-large-v3")
CLEAN_MODEL = os.getenv("MODEL", "openai/gpt-oss-120b")

HINT = (
    "Nigerian Pidgin English. Emeka dey owe me one million naira. "
    "I don sell three bag of rice to Mama Chidi, she no pay me yet. "
    "Oga Emeka don pay 45k. Abeg make you add pepper, I buy am for twelve thousand."
)

CLEANUP = """You fix speech-to-text errors in transcripts of Nigerian market traders
speaking Nigerian Pidgin or English. The transcriber does not understand Pidgin, so
Pidgin words are often misheard as similar-sounding English words or names.

Common Pidgin: dey (is/are/am), don (already), no (not), wetin (what), na (it is),
abeg (please), oga (boss), sabi (know), wan (want), am (it), pay (pay), owe, collect.

Rules:
- Fix only words that are clearly misheard. Keep the speaker's wording otherwise.
- Do not invent names, items, numbers or amounts. Never add new information.
- Example: "Emeka de Oomi one million" becomes "Emeka dey owe me one million".
- Return ONLY the corrected transcript. No quotes, no explanation."""


def clean_transcript(text: str) -> str:
    try:
        r = client.chat.completions.create(
            model=CLEAN_MODEL,
            messages=[
                {"role": "system", "content": CLEANUP},
                {"role": "user", "content": text},
            ],
            temperature=0,
            reasoning_effort="low",
        )
        fixed = r.choices[0].message.content.strip().strip('"')
        if not fixed or len(fixed) > 2 * len(text) + 20:
            return text
        return fixed
    except Exception as ex:
        print("CLEANUP ERROR:", repr(ex))
        return text


def transcribe(filename: str, audio: bytes) -> str:
    result = client.audio.transcriptions.create(
        file=(filename, audio),
        model=STT_MODEL,
        language="en",
        prompt=HINT,
        response_format="text",
        temperature=0,
    )
    raw = (result if isinstance(result, str) else result.text).strip()
    print("RAW:", raw)
    fixed = clean_transcript(raw) if raw else raw
    print("CLEAN:", fixed)
    return fixed