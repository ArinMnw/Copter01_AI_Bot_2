import json, sys
N = sys.argv[1]
with open(f"strategy/s20.{N}/result_365d.json", "r", encoding="utf-8") as f:
    res = json.load(f)
META = res.get("meta", {})
parents = META.get("parents", [])
parent_A = parents[0].split(".")[1]
parent_B = parents[1].split(".")[1]

with open(f"strategy/s20_gen/result_365d.json", "r", encoding="utf-8") as f:
    all_res = json.load(f)

res_A = all_res.get(parent_A, {}).get("tfs", {})
res_B = all_res.get(parent_B, {}).get("tfs", {})

out_lines = []
ok = True
fail_reason = ""
for tf, data in res.get("tfs", {}).items():
    if data.get("verdict") == "PASS":
        pf_mix = data.get("pf", 0)
        net_mix = data.get("net", 0)
        trades = data.get("trades", 0)
        
        pf_A = res_A.get(tf, {}).get("pf", 0)
        net_A = res_A.get(tf, {}).get("net", 0)
        pf_B = res_B.get(tf, {}).get("pf", 0)
        net_B = res_B.get(tf, {}).get("net", 0)
        
        best_pf = max(pf_A, pf_B)
        best_net = max(net_A, net_B)
        
        if pf_mix < best_pf + 0.10 or net_mix < best_net:
            ok = False
            fail_reason = f"a (PF/Net worse on {tf})"
        if trades < 50:
            ok = False
            fail_reason = f"b (Trades {trades} < 50 on {tf})"

if ok:
    with open(f"strategy/s20.{N}/mix_check.txt", "w", encoding="utf-8") as f:
        f.write("MIX_OK\n")
else:
    with open(f"strategy/s20.{N}/mix_check.txt", "w", encoding="utf-8") as f:
        f.write(f"MIX_FAIL: ข้อ {fail_reason}\n")
