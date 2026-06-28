# Looper Skills Guide

A complete, no-experience-required walkthrough of the Skills system: what a Skill is, what the
Skill Shop is for, three worked examples, and exact click-by-click steps to create one yourself.

---

## 1. What is a Skill?

A **Skill** is a reusable capability you can teach one of your agents, which can then optionally
be shared with other agents. Every Skill is made of up to two parts:

1. **Instructions** (always available) — a block of plain-text/markdown guidance that gets
   merged directly into the agent's "soul"/system prompt whenever the agent has the skill
   active. This is the simplest kind of Skill: no code at all, just knowledge or rules you want
   the agent to always remember and follow. For example, "always format dates as YYYY-MM-DD" or
   "our company's refund policy is X."

2. **A custom tool** (optional) — a small piece of Python code that becomes an actual button the
   agent can press — i.e. a new tool it can call mid-task, the same way it already calls its
   built-in file/shell/browser tools. You write the code; Looper turns it into a tool the agent
   can invoke with arguments you define.

A Skill can have just instructions, just a custom tool, or both. Most simple Skills are
instructions-only — you only need to write code if you want the agent to be able to *do* a new
concrete thing (calculate something, transform some text, etc.) rather than just *know*
something.

**Important safety rule:** if a Skill includes a custom tool, every single time any agent tries
to actually use that tool, the action pauses and shows up in your **Approvals** inbox for you to
approve or deny — every time, not just the first time. This is because custom tool code is
written by you or another agent (not vetted by Looper itself), so it's treated with the same
caution as any other risky action.

**Who owns a Skill?** Whichever agent's page you created it from. That agent is automatically
allowed to use it immediately — no approval needed for your own creation. Other agents do not get
it automatically; you have to grant it to them (see Section 4).

**Visibility levels**, set when you create a Skill:
- **Private** — only the owning agent can ever use it.
- **Company** — a label meaning "this belongs to the company," but in the current UI it behaves
  the same as Private (only the owner can use it) — there's no extra sharing step for this level
  yet.
- **Skill Shop** — the only level that can actually be shared with *other* agents (in the same
  company or a different one). Shop skills appear on the global Skill Shop page, where you can
  grant them to any agent, and agents themselves can ask for them (see Section 4).

So in practice today: if you want only one agent to ever use a Skill, pick Private. If you want
to eventually hand it to other agents too, pick Skill Shop.

---

## 2. What is the Skill Shop?

The Skill Shop is one shared page (linked "Skill Shop" in the top navigation bar of the Looper
web app) listing every Skill anyone has published with Skill Shop visibility, regardless of which
company created it. From that page you can:

- See each shop Skill's name, description, and whether it includes a custom tool.
- **Grant** it directly to any agent in any of your companies, instantly (no approval needed,
  since you are the one doing the granting).
- **Export** it to a `.skill.json` file you can keep or hand to someone else.

Separately, an agent can also *ask for* a shop Skill on its own initiative, using a built-in tool
called `request_skill`. If it does this, the request shows up in your **Approvals** inbox as a
"skill grant" request, and the Skill won't become active for that agent until you approve it
there.

---

## 3. Three example Skills

These are real, working examples — copy them exactly if you want to try them yourself.

### Example 1: "Brand Voice Guide" (instructions only, no code)

**Use case:** You have a writer agent and you want every piece of text it produces to follow the
same tone and formatting rules, without having to repeat those rules in every single instruction
you give it.

- **Name:** `Brand Voice Guide`
- **Description:** `House style rules for all written content`
- **Instructions:**
  ```
  When writing any customer-facing text:
  - Use a warm, plain-spoken tone. No corporate jargon.
  - Write numbers below 10 as words (e.g. "three", not "3").
  - Always sign off documents with "— The Team", not your own name.
  - Avoid exclamation marks entirely.
  ```
- **Custom tool source:** leave blank — this Skill is pure knowledge, no new tool needed.

Once granted, the agent will simply follow these rules automatically on every task from then on.

### Example 2: "Word & Character Counter" (a real custom tool)

**Use case:** Language models are often imprecise at counting things in their own head. This
Skill gives the agent an exact, reliable counting tool instead of guessing.

- **Name:** `Word Counter`
- **Description:** `Counts words and characters in a piece of text exactly`
- **Instructions:** `Use the word counter tool whenever asked for an exact word or character count — never estimate by eye.`
- **Custom tool source:**
  ```python
  def run(args, company_folder):
      text = args.get("text", "")
      words = len(text.split())
      chars = len(text)
      chars_no_spaces = len(text.replace(" ", ""))
      return f"Words: {words}, Characters (with spaces): {chars}, Characters (no spaces): {chars_no_spaces}"
  ```
- **Custom tool parameter schema:**
  ```json
  {"type": "object", "properties": {"text": {"type": "string", "description": "The text to count"}}, "required": ["text"]}
  ```

### Example 3: "Currency Converter" (a custom tool with its own small data table)

**Use case:** A finance- or research-focused agent that regularly needs to convert amounts
between a handful of currencies, without needing real internet access.

- **Name:** `Currency Converter`
- **Description:** `Converts an amount between a small set of supported currencies using fixed rates`
- **Instructions:** `Use the currency converter tool for any currency conversion request. Supported currencies: USD, EUR, GBP, JPY.`
- **Custom tool source:**
  ```python
  def run(args, company_folder):
      rates = {"USD": 1.0, "EUR": 0.92, "GBP": 0.79, "JPY": 149.5}
      amount = args.get("amount", 0)
      from_currency = args.get("from_currency", "USD").upper()
      to_currency = args.get("to_currency", "USD").upper()
      if from_currency not in rates or to_currency not in rates:
          return f"Unknown currency. Supported: {', '.join(rates.keys())}"
      usd_amount = amount / rates[from_currency]
      converted = usd_amount * rates[to_currency]
      return f"{amount} {from_currency} = {round(converted, 2)} {to_currency}"
  ```
- **Custom tool parameter schema:**
  ```json
  {"type": "object", "properties": {"amount": {"type": "number"}, "from_currency": {"type": "string"}, "to_currency": {"type": "string"}}, "required": ["amount", "from_currency", "to_currency"]}
  ```

A technical note on writing your own custom tool code: it runs in a deliberately restricted
sandbox that does **not** allow `import` statements or access to the network/filesystem directly
— you only get basic Python (numbers, text, lists, dictionaries, loops, `len`, `round`, `sorted`,
and a few similar built-ins). This keeps things safe, but means a custom tool can't fetch live web
data or read files itself — for that, point the agent at its existing file/browser tools instead,
and use Skills for self-contained logic like the two examples above.

---

## 4. Step-by-step: creating a Skill yourself

1. Open Looper in your browser and go to the company that has the agent you want to teach.
2. Click that agent's name in the org chart to open its **agent detail page**.
3. Scroll down to the card titled **"Skills owned by \<agent name\>."**
4. Click **"Create a new skill"** to expand the form.
5. Fill in the fields:
   - **Name** — required. A short label, e.g. `Word Counter`.
   - **Description** — a one-line summary. Shown later in the Skill Shop and to the agent itself.
   - **Instructions** — optional markdown/plain text merged into the agent's system prompt. Leave
     blank if this Skill is code-only.
   - **Custom tool Python source** — optional. Leave blank for an instructions-only Skill. If you
     want a real tool, paste Python code that defines a function called exactly `run(args, company_folder)`
     and `return`s a string result — see the examples above.
   - **Custom tool parameter schema** — only needed if you filled in custom tool source. This is a
     JSON Schema describing what arguments the agent should pass in. Match it to what your `run`
     function reads out of `args`.
   - **Visibility** — choose `Private` (only this agent, ever), `Company` (currently behaves the
     same as Private), or `Skill Shop` (shareable with other agents — see Section 2).
6. Click **"Create Skill."**

That's it — the owning agent can use it immediately. If you set visibility to anything other than
Skill Shop, you're done; nobody else will ever see it.

### If you chose "Skill Shop" visibility and want to give it to another agent

1. Click **"Skill Shop"** in the top navigation bar.
2. Find your Skill's card in the list.
3. Use the **"Grant to agent..."** dropdown to pick the agent you want to give it to (this list
   includes agents from every company you've created, not just the one you started from).
4. Click **"Grant."**

The Skill is now active for that agent immediately — no approval step, because you're the one
granting it directly.

### Letting an agent ask for a shop Skill itself

You don't have to do anything extra to enable this — any agent can already see the list of
available Skill Shop items and call its `request_skill` tool on its own if it decides it needs
one (for example, if you tell it "you'll need to convert some currencies for this report" and it
notices a Currency Converter Skill exists in the shop). When it does:

1. A new item appears in your **Approvals** inbox (and, if you're using the Android app, you'll
   get a notification) describing which agent wants which Skill.
2. Open that item, review what you're approving, and click **Approve** or **Deny**.
3. If approved, the Skill is active for that agent from then on.

### Using a custom-tool Skill once it's active

Nothing further to set up — once a Skill with a custom tool is active for an agent, that tool is
automatically available the next time the agent starts a new task. Two things to remember:

- A Skill granted **while a task is already running** won't apply to that already-in-progress
  task — it takes effect starting with the agent's *next* task.
- Every time the agent actually calls the custom tool, you'll see it pause for approval in your
  Approvals inbox, exactly like any other risky action. This happens on every use, not just the
  first time — review the tool name and the arguments it's being called with before approving.

### Exporting and importing a Skill

On the agent detail page (under "Skills owned by...") or the Skill Shop page, click **Export**
next to any Skill to download it as a `.skill.json` file. To bring one back in — for example, on
a different agent or after sharing the file with someone — open the target agent's detail page,
expand **"Import a .skill.json file,"** choose the file, pick a visibility, and click **Import.**
This creates a brand-new Skill owned by that agent (not a link back to the original), so the two
copies are independent from that point on.
