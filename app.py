from flask import Flask, jsonify
import requests
import time

app = Flask(__name__)

API_GOC = "https://wtxmd52.macminim6.online/v1/txmd5/lite-sessions?cp=R&cl=R&pf=web&at=7aa1c7e7ea0160fd97524740774a4c61"

cache = None
cache_time = 0

# ===== MODEL =====
def get_markov_prob(order, hist):
    if len(hist) < order + 1:
        return 0.5

    trans = {}
    for i in range(order, len(hist)):
        key = ''.join(hist[i-order:i])
        if key not in trans:
            trans[key] = {"TAI": 0, "XIU": 0, "total": 0}

        nxt = hist[i]
        trans[key][nxt] += 1
        trans[key]["total"] += 1

    last_key = ''.join(hist[-order:])
    if last_key in trans and trans[last_key]["total"] > 0:
        return trans[last_key]["TAI"] / trans[last_key]["total"]

    return 0.5


def get_ngram_prob(n, hist):
    if len(hist) < n + 1:
        return 0.5

    last_n = ''.join(hist[-n:])
    matches = 0
    tai_after = 0

    for i in range(n, len(hist)):
        seq = ''.join(hist[i-n:i])
        if seq == last_n:
            matches += 1
            if hist[i] == "TAI":
                tai_after += 1

    return tai_after / matches if matches > 0 else 0.5


def calc_accuracy(model_fn, hist):
    if len(hist) < 12:
        return 0.55

    correct = 0
    total = 0

    for i in range(8, len(hist)):
        sub = hist[:i]
        p = model_fn(sub)
        pred = "TAI" if p > 0.5 else "XIU"

        if pred == hist[i]:
            correct += 1
        total += 1

    return correct / total if total > 0 else 0.55


def predict(hist):
    if len(hist) < 8:
        p = hist.count("TAI") / len(hist) if hist else 0.5
        return "TAI" if p > 0.5 else "XIU", 60

    models = [
        lambda h: h[-60:].count("TAI") / len(h[-60:]),
        lambda h: get_markov_prob(1, h),
        lambda h: get_markov_prob(2, h),
        lambda h: get_markov_prob(3, h),
        lambda h: get_ngram_prob(3, h),
        lambda h: get_ngram_prob(4, h),
    ]

    accuracies = [calc_accuracy(m, hist) for m in models]

    weighted = 0
    total_w = 0

    for i, m in enumerate(models):
        p = m(hist)
        acc = accuracies[i]
        weighted += p * acc
        total_w += acc

    final_prob = weighted / total_w if total_w > 0 else 0.5

    last = hist[-1]
    streak = get_markov_prob(1, hist)

    if last == "TAI":
        final_prob = final_prob * 0.85 + streak * 0.15
    else:
        final_prob = final_prob * 0.85 + (1 - streak) * 0.15

    prediction = "TAI" if final_prob > 0.5 else "XIU"

    confidence = int(60 + (sum(accuracies)/len(accuracies)) * 30)
    confidence = max(52, min(95, confidence))

    return prediction, confidence


# ===== API =====
@app.route("/api")
def api():
    global cache, cache_time

    if time.time() - cache_time < 5 and cache:
        return jsonify(cache)

    try:
        res = requests.get(API_GOC)
        data = res.json()

        sessions = data.get("data", [])

        history = []
        for s in sessions:
            total = int(s["total"])
            history.append("TAI" if total >= 11 else "XIU")

        # ===== LẤY PHIÊN GẦN NHẤT =====
        last = sessions[0]

        phien_truoc = int(last["id"])
        tong_xuc_xac = int(last["total"])
        phien_tiep = phien_truoc + 1

        du_doan, do_tin_cay = predict(history)

        result = {
            "phien_truoc": phien_truoc,
            "tong_xuc_xac": tong_xuc_xac,
            "phien_tiep_theo": phien_tiep,
            "du_doan": du_doan,
            "do_tin_cay": f"{do_tin_cay}%"
        }

        cache = result
        cache_time = time.time()

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)})