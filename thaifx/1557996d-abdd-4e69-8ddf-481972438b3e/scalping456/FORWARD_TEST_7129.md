# Scalping456 migration — 2459 to 7129

วันที่ 15 ตุลาคม 2026 พี่สั่งหยุด monitor และย้าย Scalping456 จากโปรไฟล์ 2459 ไป 7129

## Scope and configuration

| Item | Source | Destination |
|---|---|---|
| Profile | `demo-iux-2101182459` | `demo-exness-434237129` |
| Login / server | `2101182459` / `IUXMarkets-Demo` | `434237129` / `Exness-MT5Trial7` |
| Exact gold symbol | `XAUUSD.iux` | `XAUUSDm` |
| New Scalping456 entries | Disabled; production wrapper is drain-only even with stale ON flag | Enabled in profile.env |
| Other portfolio flags at edit | `LTS_AHR2` preserved | `INDI1,EA2_1` preserved |

- Magic remains `995456`, fixed lot `0.01`. State and journal are local to each profile: `scalping456_state.json` and `logs/scalping456_events.jsonl`.
- Do not copy IUX state, order IDs, history, daily PnL, or the completed three-position monitor baseline into Exness. The target adapter creates fresh state on its first working cycle.
- Existing broker positions are not transferable between accounts. No market positions were closed and no foreign pending orders were modified for this migration.
- Account/server/demo/hedging/terminal-path checks run before every adapter trade request. Only these two exact profiles are allowlisted; old 2459 remains supported to protect/drain owned positions, not open new cycles.
- Scheduler and cooperative shutdown hooks now cover both allowlisted profiles; max_instances remains 1 and coalesce remains True.

## Broker preflight (read-only)

Before changes, an already-running portable terminal was verified for each exact profile. Native API account identities matched the table and both were Demo/hedging accounts.

- IUX: 100 foreign positions, zero Scalping456 positions/pending orders in the observed snapshot. Keep all foreign trades untouched.
- Exness: zero positions and seven foreign pending orders, magic `234001`, in the observed snapshot. No magic `995456` collision found. These are point-in-time observations, not frozen counts.
- `XAUUSD` does not exist on this Exness account. Verified native symbol is visible `XAUUSDm`, digits 3, point/tick `0.001`, lot min/step `0.01`, contract size 100, stop/freeze levels 0. No symbol selection or login/account switch was performed by the audit.
- Price-distance parameters stay unchanged: native BUY_STOP=Ask+1.30, SELL_STOP=Bid-1.30; initial SL distance 1.00, TP=0. Trailing activation >0.20, distance 0.20, improvement >0.01, first-seen delay 0.900s, minimum modify interval 0.270s. Prices use this broker's tick rounding, not IUX point counts.
- Max own positions plus pending exposure 3; confirmed daily net loss gate -20 USD blocks new entries, not a guaranteed loss ceiling or forced liquidation. No feed offsets or account-balance lot scaling added.

## Monitor and activation

The original automation `scalping456-demo-2459-3` is **PAUSED**. No 7129 monitor was created or enabled. The original three-position ledger and broker evidence remain under `data/forward_2459_20261015/`.

At migration preparation, both previous main processes/supervisors were already stopped and intentional-stop markers were present. This task does not override those stop markers or launch/restart another portfolio on the user's behalf. Start the destination using its normal `run/run_supervised.bat` after preparation. The supervisor must reload profile.env; a child-only restart under a supervisor holding old environment values is insufficient.

Prepared configuration is not proof of live execution. Read the dated migration manifest for the final verification status. A follow-up runtime check must confirm a fresh 7129 heartbeat, matching native account identity, journal acknowledgements and native protected pending/fill records before claiming live success.

This remains an experimental adapter, not a verified 100% clone of the original EA and not a profitability claim.

## Final preparation check — 14:43 BKK

Status: **PREPARED, AWAITING FULL 7129 SUPERVISOR RESTART**. [Migration manifest](data/forward_7129_20261015/migration_manifest.json) records the exact account, code hashes, flags and checks.

- During preparation, 7129 was started outside this task: supervisor PID 36444, main PID 41428. Its heartbeat is fresh and MT5 connection is healthy, but persisted runtime still reports `INDI1=True`, `EA2_1=True`, `SCALPING456=False`. No target Scalping456 state or owned pending/position exists yet. It has not loaded the new portfolio environment; do not call this live-forward success.
- Required next step: Stop and start `profiles/demo/demo-exness-434237129/run/run_supervised.bat` so the supervisor reloads profile.env. Do not use the 2459-only restart helper for 7129. There is no need to start 2459 for Scalping456.
- Fresh-process config checks resolve source active list to `LTS_AHR2` and target active list to `INDI1,EA2_1,SCALPING456`, with explicit environment override of old bot_state flags.
- Mock suite: **52 unittest tests PASS**, including seven target migration tests and an additional target cooperative-restart isolation test; the imported legacy demo-manager regression reports **10 cases PASS**. Python compile, git diff whitespace check, and scoped UTF-8/LF/mojibake checks pass.
- Full `verify_repo.py` did not finish within the bounded 45s repository-wide checker attempt. Its two orphaned text-check processes were stopped after exact PID/creation-time/parent/command checks. No trading process was stopped. Do not report full repository verification as passed.
- Read-only target native preflight passes with USD account currency, visible `XAUUSDm`, no owned exposure and no magic collision. Latest snapshot has eight foreign pendings; none were modified. No order_send, symbol selection, account switch, bot restart or Telegram action was performed by this task.
- Monitor remains **PAUSED**, with no new monitor scheduled for 7129.
