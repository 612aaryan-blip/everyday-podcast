import os, sys, time
from gtts import gTTS
from gtts.tokenizer import pre_processors, Tokenizer, tokenizer_cases

HERE = os.path.dirname(os.path.abspath(__file__))
PARTS = os.path.join(HERE, ".parts")
os.makedirs(PARTS, exist_ok=True)
text = open(os.path.join(HERE, "today.txt")).read().strip()

t = gTTS(text=text, lang="en", tld="com")
chunks = t._tokenize(text)
open(os.path.join(PARTS, "count.txt"), "w").write(str(len(chunks)))

deadline = time.time() + float(sys.argv[1]) if len(sys.argv) > 1 else time.time() + 150
done = 0
for i, c in enumerate(chunks):
    p = os.path.join(PARTS, f"p{i:03d}.mp3")
    if os.path.exists(p) and os.path.getsize(p) > 0:
        done += 1
        continue
    if time.time() > deadline:
        break
    for attempt in range(3):
        try:
            gTTS(text=c, lang="en", tld="com").save(p)
            done += 1
            break
        except Exception as e:
            if attempt == 2:
                print("FAIL", i, e)
            time.sleep(1)
print(f"{done}/{len(chunks)} chunks ready")
