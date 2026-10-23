import tempfile
from core.db import Database
from core.logic import score_questions,normalize_count,chunk_text
from core.validation import QuizPayload,Flashcard
def test_count_and_score():
    assert normalize_count(25)==25
    try: normalize_count(50); assert False
    except ValueError: pass
    qs=[{"question":"x","correct_answer":"A"},{"question":"y","correct_answer":"B"}]
    r=score_questions(qs,{0:'A'}); assert r['correct']==1 and r['unanswered']==1
def test_validation():
    q={"question":"Q","options":{"A":"1","B":"2","C":"3","D":"4"},"correct_answer":"A","explanation":"ok"}
    assert len(QuizPayload(questions=[q]).questions)==1
    assert Flashcard(front='q',back='a').rating=='Needs Review'
def test_db_and_chunks():
    with tempfile.NamedTemporaryFile(suffix='.db') as f:
        db=Database(f.name); sid=db.add_source('t','text','hello world'); assert db.sources()[0]['id']==sid
        db.save('notes','n',{'text':'x'}); assert len(db.artifacts('notes'))==1
    assert len(chunk_text('a'*100,30,5))>1
