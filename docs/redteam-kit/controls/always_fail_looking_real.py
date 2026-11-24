import json, sys
ids = ["S1","S2","S3","S4","S5","S6","S8","S11"]
print(json.dumps({"implementer": "control/always-fail-looking-real", "result": "FAIL",
                  "checks": [{"id": i, "result": "FAIL"} for i in ids]}))
sys.exit(1)
