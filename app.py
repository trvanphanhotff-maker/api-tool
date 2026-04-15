l from flask import Flask, Response
import requests
import math

app = Flask(__name__)

API_URL = "https://wtxmd52.macminim6.online/v1/txmd5/lite-sessions?cp=R&cl=R&pf=web&at=7aa1c7e7ea0160fd97524740774a4c61"

MAX_HISTORY = 200
history = []

# ================= FETCH GIỐNG HTML =================
def fetch_sessions():
    global history
    try:
        res = requests.get(API_URL, timeout=5)
        data = res.json()

        if "list" not in data:
            return None

        new_sessions = [{
            "id": s["id"],
            "result": s["resultTruyenThong"],
            "_id": s.get("_id", "unknown"),
            "point": s.get("point", "unknown")
        } for s in data["list"]]

        existing_ids = set(h["id"] for h in history)
        updated = False

        # 🔥 QUAN TRỌNG: đảo ngược giống HTML
        for s in reversed(new_sessions):
            if s["id"] not in existing_ids:
                history.append(s)
                existing_ids.add(s["id"])
                updated = True

        # giữ max 200
        if len(history) > MAX_HISTORY:
            history[:] = history[-MAX_HISTORY:]

        return history[-1] if history else None

    except:
        return None


# ================= MARKOV =================
def get_markov_prob(order, hist):
    if len(hist) < order + 1:
        return 0.5

    trans = {}

    for i in range(order, len(hist)):
        key = "".join(hist[i - order:i])

        if key not in trans:
            trans[key] = {"TAI": 0, "XIU": 0, "total": 0}

        nxt = hist[i]
        trans[key][nxt] += 1
        trans[key]["total"] += 1

    last_key = "".join(hist[-order:])

    if last_key in trans and trans[last_key]["total"] > 0:
        return trans[last_key]["TAI"] / trans[last_key]["total"]

    return 0.5


# ================= NGRAM =================
def get_ngram_prob(n, hist):
    if len(hist) < n + 1:
        return 0.5

    last = "".join(hist[-n:])
    matches = 0
    tai_after = 0

    for i in range(n, len(hist)):
        seq = "".join(hist[i - n:i])

        if seq == last:
            matches += 1
            if hist[i] == "TAI":
                tai_after += 1

    return tai_after / matches if matches > 0 else 0.5


# ================= ACCURACY =================
def calculate_model_accuracy(model_fn, hist):
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


# ================= PREDICT (Y HỆT HTML) =================
def predict():
    if len(history) < 8:
        count_tai = sum(1 for h in history if h["result"] == "TAI")
        p = count_tai / len(history) if history else 0.5

        conf = round(max(52, min(68, 50 + 35 * abs(p - 0.5) * 2)))

        return ("TAI" if p > 0.5 else "XIU", conf)

    results = [h["result"] for h in history]

    models = [
        # freq recent
        lambda h: (
            sum(1 for x in h[-min(60, len(h)):] if x == "TAI") /
            len(h[-min(60, len(h)):])
        ),

        lambda h: get_markov_prob(1, h),
        lambda h: get_markov_prob(2, h),
        lambda h: get_markov_prob(3, h),
        lambda h: get_ngram_prob(3, h),
        lambda h: get_ngram_prob(4, h),
    ]

    accuracies = [calculate_model_accuracy(m, results) for m in models]

    weighted_sum = 0
    total_weight = 0

    for i, model in enumerate(models):
        pTAI = model(results)
        acc = accuracies[i]

        weighted_sum += pTAI * acc
        total_weight += acc

    finalProbTAI = weighted_sum / total_weight if total_weight > 0 else 0.5

    # 🔥 STREAK BOOST GIỐNG HTML
    lastResult = results[-1]

    if lastResult == "TAI":
        streakP = get_markov_prob(1, results)
    else:
        streakP = 1 - get_markov_prob(1, results)

    finalProbTAI = (finalProbTAI * 0.85) + (streakP * 0.15)

    prediction = "TAI" if finalProbTAI > 0.5 else "XIU"

    # 🔥 CONFIDENCE Y HỆT HTML
    avgAccuracy = sum(accuracies) / len(accuracies)

    variance = sum(
        (models[i](results) - finalProbTAI) ** 2
        for i in range(len(models))
    ) / len(models)

    confidence = round(
        58 +
        (avgAccuracy * 28) +
        ((1 - math.sqrt(variance) * 1.8) * 14)
    )

    confidence = max(52, min(99, confidence))

    if len(history) < 30:
        confidence = min(confidence, 72)

    if len(history) > 150:
        confidence = max(confidence, 68)

    return prediction, confidence


# ================= ROUTE =================
@app.route("/")
def home():
    latest = fetch_sessions()

    if not latest:
        return "API ERROR"

    pred, conf = predict()

    current_id = latest["id"]
    next_id = current_id + 1

    text = f"""admin : noname
phien_truoc : {current_id}
ma_md5 : {latest["_id"]}
tong_ket_qua : {latest["point"]}
du_doan_phien_{next_id} : {pred}
do_tin_cay : {conf}%"""

    return Response(text, mimetype="text/plain")


# ================= RUN =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
