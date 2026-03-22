import os
from dotenv import load_dotenv

load_dotenv(override=True)


from main import _solve_question

test_question = """
מעגל זרם חילופין טורי מכיל נגד של 10 אוהם, משרן בעל היגב אינדוקטיבי של 20 אוהם וקבל בעל היגב קיבולי של 5 אוהם.
המעגל מחובר למקור מתח חילופין של 100 וולט עם זווית מופע 0 מעלות.
חשב את העכבה הכוללת של המעגל, את הזרם הכולל הזורם בו (כולל זווית), ואת מפל המתח על המשרן.
"""

print("STARTING SOLVE...")
try:
    solution = _solve_question(test_question)
    print("SOLUTION:")
    print("="*60)
    print(solution)
    print("="*60)
except Exception as e:
    print(f"Error: {e}")
