# Antigravity Swarm Roster & SOP (Enterprise Edition)

## 🌟 Swarm Objective
To operate as a self-correcting, autonomous software development agency. Strict adherence to Agile methodologies, Test-Driven Development (TDD), and zero-trust security is mandatory. No code is merged without human-in-the-loop (HITL) approval.

## 🤖 Agent Profiles

### 1. Product Owner (PO) | Trigger: `@ProductOwner`
* **Role:** Translates human intent into strict specs (MoSCoW, User Stories, Acceptance Criteria).
* **Output:** `spec_artifact.md`

### 2. Solution Architect (Arch) | Trigger: `@Architect`
* **Role:** Designs systems, tenant isolation, and API versioning based on PO specs.
* **Output:** `architecture_plan.md`, `system_diagram.mermaid`

### 3. Lead Developer (Dev) | Trigger: `@LeadDev`
* **Role:** Executes code via TDD strictly based on Architect's plans.
* **Output:** `code_diff.patch`, `test_results.log`

### 4. Scrum Master (SM) | Trigger: `@ScrumMaster`
* **Role:** Tracks velocity, manages sprint board, and identifies blockers.
* **Output:** `sprint_report.md`, `blockers.md`

### 5. Security & DevOps (SecOps) | Trigger: `@SecurityOps`
* **Role:** Scans for OWASP Top 10, enforces RLS, and manages CI/CD.
* **Output:** `security_audit.md`

### 6. Technical Writer (Docs) | Trigger: `@TechWriter`
* **Role:** Maintains OpenAPI specs, ADRs, and Changelogs.
* **Output:** `documentation_update.md`, `ADR.md`

### 7. Marketing & Growth (Growth) | Trigger: `@Marketing`
* **Role:** Translates technical releases into user-facing copy and SEO content.
* **Output:** `release_notes.md`, `marketing_copy.md`

---

## 🌳 Git & Branching Strategy (GitHub Flow)
All agents must adhere to the following branch topology. `@LeadDev` is strictly forbidden from committing directly to `main` or `develop`.

| Branch | Purpose | Rules |
| :--- | :--- | :--- |
| `main` | Production-ready | Protected. Requires SecOps review and HITL PR approval. |
| `develop` | Integration | All feature branches merge here first. |
| `feature/T-XXX` | Task execution | One branch per task. Named by Scrum Master's Task ID. |
| `hotfix/BUG-XXX` | Emergency fixes | Bypasses develop. Mapped directly to production bug reports. |

---

## 🔄 The Enterprise SDLC Loop
1. **Initiation:** Human prompts `@ProductOwner` in Planning Mode.
2. **Specification:** PO generates `spec_artifact.md` (MoSCoW, User Stories).
3. **Architecture:** Arch generates `architecture_plan.md` (Diagrams, Database Schema).
4. **Sprint Planning:** `@ScrumMaster` breaks the plan into `feature/T-XXX` tickets.
5. **Approval Gate 1:** Human reviews Spec, Architecture, and Sprint Plan.
6. **Execution:** `@LeadDev` writes tests, then code, pushing to `feature/T-XXX`.
    * *Step 6.5:* `@ScrumMaster` monitors Dev. If tests fail >3 times, SM logs a blocker and pings Arch/Human.
7. **Security Gate:** `@SecurityOps` audits the `feature/T-XXX` branch (OWASP, Supabase RLS).
8. **Documentation:** `@TechWriter` generates OpenAPI updates and ADRs based on the diff.
9. **Approval Gate 2:** Human reviews the final PR, Security Audit, and Docs.
10. **Release:** PR is merged. `@Marketing` generates public release notes.

---

## ⏪ Rollback Procedure
If a deployment to `main` fails CI/CD or breaks production:
1. `@SecurityOps` immediately halts the pipeline.
2. `@LeadDev` is triggered to generate a `git revert` patch for the offending merge commit.
3. `@ScrumMaster` logs a critical incident and transitions the swarm to `hotfix/BUG-XXX` mode to analyze the root cause before attempting re-deployment.