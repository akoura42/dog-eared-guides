# Phone Verification Agent — Build Plan

Status: **DECIDED / DEFERRED.** All owner decisions are resolved (§11);
nothing is built yet. Build begins after Tahoe City content batches grow
the verified pile — revisit when the phone-queue backlog justifies it
(currently 4 queued numbers). This document is the plan of record.

## 1. Goal

An AI voice agent, running entirely on the owner's M3 Ultra (512GB) —
this machine — that calls venues to verify dog policies, answers venue
callbacks on the same number, and feeds structured outcomes into the
research ledger as tier-1 (`method: phone`) verifications with published
transcript notes as the source.

**Success =** a queued ledger candidate goes from `unverifiable` to a
publishable verification (or a confirmed `rejected-no-dogs`/`closed`) via
an automated call whose transcript and structured summary a human audits
before anything ships. The human-review PR gate is unchanged — the agent
produces evidence, never published pages.

## 2. Non-goals

- No cold outreach, sales, or promotion — verification questions only.
- No audio recordings kept (transcripts only; see §8).
- **No voicemail messages, ever** (owner decision) — unanswered calls get
  the retry policy, nothing else.
- No IVR wrestling in v1: if a phone tree appears, log `ivr-blocked`,
  hang up politely; those venues go on the human call list.
- No mass-dialing. Low volume (≈5–30 outbound calls per city launch), one
  outbound call at a time in v1. (Inbound is always-on — see §4.)
- Not a replacement for web verification — phone is the tier-3 → tier-1
  escalation path when the web fails.

## 3. Volume assumptions & cost

- Current backlog: 4 numbers queued in the Tahoe City ledger
  (Bridgetender, TCPUD re: phantom dog park, Blue Fish, Coffee
  Connexion); expect 10–30 calls per future city launch plus occasional
  re-verifications and inbound callbacks.
- Inference: $0 (local). Telephony: one national Telnyx number (~$1–2/mo)
  + ~1¢/min (≈ $2–5 per city launch). Total system cost ≈ the number rental.

## 4. Architecture

```
                    OUTBOUND                          INBOUND (24/7)
        Telnyx number ── media stream ─┐   ┌── venue calls the same number
                                       ▼   ▼
                            cloudflared tunnel (auto-restart)
                                       │
              ┌──────────── Pipecat pipeline (macOS daemon) ────────────┐
              │  VAD → STT (parakeet-mlx) → LLM (Qwen3-30B-A3B, MLX)    │
              │        ← TTS (Kokoro-82M) ←        │                    │
              │  inbound: caller-ID → ledger lookup → venue context;    │
              │  unknown caller → generic flow + transcribed message    │
              └────────────────────────────────────┼────────────────────┘
                                                   ▼
                              structured CallOutcome JSON
                                                   ▼
              pipeline/ledger/ (checks.jsonl + place status + transcript)
                                                   ▼
        human review → transcript note published → venue file → PR → merge
```

**24/7 daemon** (owner decision): the agent + tunnel run continuously on
this machine as a `launchd` service wrapped in `caffeinate`, with
auto-restart on crash and a health-check ping. Inbound callbacks always
reach the live agent; since we never leave voicemail, most callbacks are
missed-call returns ("someone from this number called me?") — the inbound
script opens by explaining exactly that.

## 5. Component choices (all open source, all local)

| Layer | Choice | License | Notes |
|---|---|---|---|
| Orchestration | Pipecat | BSD-2 | Interruption/barge-in, VAD, turn-taking; Telnyx transport built in |
| Telephony | **Telnyx** (decided), one national number | n/a (carrier) | Same number outbound caller-ID and inbound; `cloudflared` tunnel exposes the local agent |
| STT | parakeet-mlx (Parakeet TDT 0.6B v2) | CC-BY-4.0 weights | Real-time on Apple Silicon; fallback: whisper.cpp large-v3-turbo |
| LLM | Qwen3-30B-A3B via mlx-lm (OpenAI-compatible server) | Apache 2.0 | ~3B active params → fast TTFT. Fallback: Qwen3-14B if latency misses budget |
| TTS | Kokoro-82M | Apache 2.0 | Faster than real-time; natural enough for a utility call |

Latency budget per turn (target ≤ 1.5s perceived): VAD endpoint ~200ms +
STT ~150ms + LLM TTFT ~300–500ms + TTS first-audio ~150ms. Measured in
Phase 0; models stay resident (~25GB of 512GB) since the daemon is 24/7.

## 6. Call design

### Outbound script skeleton (state machine, not freeform chat)

1. **Disclosure (mandatory, verbatim):** "Hi — I'm an automated assistant
   calling on behalf of Dog-Eared Guides, a travel guide. I have one quick
   question about your dog policy; this call isn't recorded. Is now okay?"
   - If no / annoyance / confusion → thank + end (`declined`).
2. **The question** (from the ledger row): "Do you allow dogs at [venue] —
   for example on a patio or in outdoor areas?"
3. **Clarifiers** (max 2, only if relevant): where exactly; leash rules;
   fees; seasonal limits.
4. **Verbatim read-back (mandatory):** "So to confirm: [restatement]. Is
   that right?" — an outcome is only `confirmed` if the human affirms the
   read-back; all numbers repeated digit-by-digit. The anti-hallucination gate.
5. **Close:** thank; honor "take us off your list" instantly and
   permanently (`do-not-call` flag in the ledger row).

### Inbound script skeleton

1. **Disclosure:** "Thanks for calling back — this is the automated
   assistant for Dog-Eared Guides, a travel guide. This call isn't
   recorded."
2. **Caller-ID lookup** against numbers we've dialed → if matched:
   "We called with one quick question about [venue]'s dog policy — do you
   have a moment?" → continue at outbound step 2.
3. **Unknown caller:** brief explanation of who we are; offer to take a
   message (transcribed to the ledger for the owner); never collect
   personal data beyond a business callback context.
4. Same read-back gate, same close.

### Operational rules

- Outbound window: 10:00–16:00 **venue-local** time, weekdays; skip
  11:30–13:30 for eat/drink venues. (Inbound answers whenever it rings.)
- Max 2 outbound attempts per venue per batch, ≥2 days apart. **Voicemail
  detected → hang up, log `no-answer`. Never leave a message.**
- One concurrent outbound call. Hard call timeout: 5 minutes.
- Any human distress/confusion → immediate polite exit; never argue.

### CallOutcome schema (the LLM's required structured output)

```json
{
  "place_id": "osm-blue-fish-pok",
  "direction": "outbound | inbound",
  "outcome": "confirmed | denied-dogs | no-answer | ivr-blocked | wrong-number | declined | unclear | do-not-call | message-taken",
  "policy": {"allowed": "patio_only|indoors|outdoor_areas|grounds_only|no|null",
              "leash_required": null, "fee": null, "notes": "verbatim-as-possible answer"},
  "respondent_role": "e.g. host, manager, unknown",
  "readback_affirmed": true,
  "call_ts": "ISO-8601",
  "duration_s": 0
}
```

## 7. Ledger & site integration

- Every call appends to `pipeline/ledger/checks.jsonl` (actor:
  `phone-agent`) and saves a transcript to
  `pipeline/ledger/transcripts/<place_id>-<date>.md`.
- `readback_affirmed: true` outcomes update the place row — but a human
  reads the transcript before any venue file is written; files land in a
  normal content PR.
- **Transcripts are published** (owner decision): a `verification-notes`
  content collection renders each approved transcript note at
  `/verification-notes/<id>/`, and the venue's
  `verification.source_url` for `method: phone` points at that URL. This
  keeps `source_url` required exactly as-is — **no schema change needed**
  (the previously-planned nullable-for-phone change is dropped) — and
  turns every phone verification into a visible trust artifact.
- The `DogPolicyBlock` "by phone" label already exists; the only site
  work is the small `verification-notes` collection + page template
  (built during Phase 5, not before).

## 8. Compliance & etiquette (non-negotiable)

- **Disclose the bot** at the top of every call, outbound and inbound
  (California B.O.T. Act; also just honest).
- **No audio recording.** California is all-party-consent; we keep live
  transcripts only, and the disclosure says so.
- B2B, low-volume, human-triggered verification calls — no autodialer
  patterns; `do-not-call` flags honored permanently.
- The published transcript note is a cleaned summary transcript, not a
  recording; it names the venue and date, never the employee.

## 9. Build phases & acceptance criteria

| Phase | Work | Done when |
|---|---|---|
| **0. Bench** | Install mlx-lm + Qwen3-30B-A3B, parakeet-mlx, Kokoro; measure turn latency end-to-end | p50 turn latency ≤1.5s; models pinned in a requirements note |
| **1. Dialog sim** | Outbound + inbound state machines + CallOutcome schema, text-only. Adversarial sim: second local model plays the staffer across ≥10 scenarios (incl. inbound known/unknown caller) | ≥90% correct schema-valid outcomes; zero invented policies |
| **2. Local audio loop** | Pipecat mic↔speaker, no telephony; barge-in works | Natural human role-play; interruptions handled |
| **3. Telephony (outbound)** | Telnyx number + media streams + cloudflared; agent calls **owner's own phone** | 5 clean test calls incl. voicemail-detect-and-hangup and mid-call hangup |
| **3b. Inbound** | Same number answered by the agent; caller-ID → ledger lookup | Owner calls in: matched-venue flow and unknown-caller flow both correct |
| **4. Supervised live** | Call the queued Tahoe City numbers, owner listening with kill switch | Transcripts + outcomes in ledger; human agrees with every outcome |
| **5. Operationalize** | `pipeline/call_agent/` CLI (`--place-id`, `--batch city`), `verification-notes` collection + template, RUNBOOK section | A phone-queue batch runs end-to-end with one command; first transcript note published |
| **5b. Daemonize** | launchd service + caffeinate + tunnel auto-restart + health check | Survives reboot; inbound reachable 24/7; a week of uptime without intervention |

Estimated effort: Phases 0–2 ≈ one focused day; 3+3b ≈ one day;
4–5b ≈ one day. Sequential, each gated on the prior.

## 10. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Model invents a policy | Read-back gate: no affirmation → `unclear`, never `confirmed` |
| Misheard numbers (fees) | Digit-by-digit repetition in the read-back |
| IVR menus | v1 punts (`ivr-blocked`); human calls those |
| Tunnel/carrier flakiness | Auto-restart + health check; outcome `no-answer` + retry policy |
| 24/7 daemon dies silently | launchd KeepAlive + health-check ping surfaced to the owner |
| Inbound abuse/spam calls | Unknown-caller flow is short, collects nothing sensitive, rate-limits repeat callers |
| Venue annoyance / reputation | Low volume, business hours, instant opt-out, no voicemail, human-quality manners |
| macOS sleep | `caffeinate` in the service definition |

## 11. Decisions (resolved 2026-08-06)

| Topic | Decision |
|---|---|
| Carrier | Telnyx |
| Caller ID | One national number for all cities |
| Voicemail | Never leave messages |
| Callbacks | Answered live by the agent (inbound in v1 scope) |
| Uptime | 24/7 daemon on this M3 Ultra |
| Supervision | Autonomous after Phase 4; transcript review before publishing |
| IVR | Punt in v1 |
| Transcripts | Published as `/verification-notes/` source pages |
| Members-only venues | Not listable (terminal ledger state; no schema/UI work) |
| Email fallback | `verify@dogearedguides.com` via Cloudflare Email Routing → Gmail; pipeline drafts, owner sends; replies = tier-1 written evidence |
| Timing | Deferred until Tahoe City content batches grow the verified pile |

## 12. Email verification channel (companion to phone)

When a venue says "email us" or is email-first: the pipeline drafts the
outreach text into the ledger note/PR; the **owner sends it manually**
from `verify@dogearedguides.com` (Cloudflare Email Routing forward →
Gmail — free, set up at build time). A reply is tier-1 written evidence:
quote + date recorded in the ledger, `method: other` with the email
exchange noted (or `official_website` when the venue points to a page).
The agent never sends email autonomously.

## 13. Out-of-scope future ideas (parking lot)

- Per-region caller-ID numbers (declined for now — one national number)
- Leaving voicemail messages (declined)
- IVR navigation (single-keypress attempts)
- Multi-city batch dialing with per-timezone scheduling
- Using the local models for menu re-parsing / ledger dedup sweeps
