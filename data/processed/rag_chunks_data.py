PROMPT_ACTION_EVENTS_BUILTIN_FILTERING = {

    "doc_type": "RULE",
    "topic": "actions_builtin_filtering",
    "priority": 90,
    "data":  """
ROUTER.RULE.actions_builtin_filtering
Intent: database record CRUD action (create/update/delete/duplicate/restore) on a window/entity record.
Output: choose EVNT_RCRD_ADD / EVNT_RCRD_UPDT / EVNT_RCRD_DEL / EVNT_RCRD_DUP / EVNT_RCRD_REST (direct action; record selection handled inside event).
Scope: record operations only.
""",

    "text": """CRITICAL: Action Events with Built-in Filtering

Use Direct Action Events (NO additional retrieve/filter needed) for:

EVNT_RCRD_ADD (Create a Record):
- Keywords: "create a record", "add a record", "create record of [entity]"
- Pattern: "create [a] record of [entity] where [conditions]"
- For complex create operations with conditions, use CNDN_BIN + EVNT_RCRD_ADD
- Examples:
  - "create a record in enrollment tracking where fee charged is 2500 to fee charged 3000" → CNDN_BIN + EVNT_RCRD_ADD (binary condition evaluates the complex fee logic)

EVNT_RCRD_DUP (Duplicate a Record):
- Keywords: "duplicate the record", "duplicate record of [entity]"
- Pattern: "duplicate [the] record of [entity] where [conditions]"
- Has BUILT-IN filtering - directly duplicates matching record
- Examples:
  - "duplicate the record of Enrollment Tracking where Title is Enrollment 1 and status is enrolled" → EVNT_RCRD_DUP ONLY
  - "duplicate a record when value is greater than 100" → EVNT_RCRD_DUP ONLY (built-in condition handling)

EVNT_RCRD_REST (Restore a Record):
- Keywords: "restore the record", "restore record of [entity]"
- Pattern: "restore [the] record of [entity] where [conditions]"
- Has BUILT-IN filtering - directly restores matching record
- Examples:
  - "restore the record of Enrollment Tracking where Title is Enrollment 1 and status is enrolled" → EVNT_RCRD_REST ONLY

EVNT_RCRD_DEL (Delete a Record):
- Keywords: "delete the record", "delete record of [entity]", "remove the record"
- Pattern: "delete [the] record of [entity] where [conditions]"
- Has BUILT-IN filtering - directly deletes matching record
- Examples:
  - "delete the record of Enrollment Tracking where Title is Enrollment 1 and status is enrolled" → EVNT_RCRD_DEL ONLY
  - "delete a record when status is expired" → EVNT_RCRD_DEL ONLY

EVNT_RCRD_UPDT (Update a Record):
- Keywords: "update the record", "update record of [entity]", "modify the record"
- Pattern: "update [the] record of [entity]"
- For update operations with conditions, use CNDN_BIN + EVNT_RCRD_UPDT
- Examples:
  - "update a record in enrollment tracking where fee charged is 2500 to fee charged 3000" → CNDN_BIN + EVNT_RCRD_UPDT (binary condition evaluates "where fee charged is 2500")

⚠️ CRITICAL RULE:
- DO NOT combine these action events with EVNT_RCRD_INFO, EVNT_FLTR, or CNDN_BIN (except for complex create operations)
- Each action event handles its own record selection and filtering internally
- Use ONLY the action event when the query is a direct action on records
- CREATE operations with complex conditions may need CNDN_BIN, CNDN_SEQ, CNDN_DOM for condition evaluation

CRITICAL ACTION DETECTION RULE:
If a query starts with "create" or contains "create a record", it is ALWAYS a CREATE operation (EVNT_RCRD_ADD), never an UPDATE operation, regardless of other words like "to" in the query.
"""
}


PROMPT_COND_OVERVIEW_AND_PATTERNS = {

    "doc_type": "RULE",
    "topic": "conditions",
    "priority": 100,
    "data": """ROUTER.RULE.conditions
Intent: conditional branching / decision logic in workflow.
Signals: if/else, when/then, otherwise, unless, first check, if not, else check.
Output: choose CNDN_BIN / CNDN_SEQ / CNDN_DOM (explicit TRUE + FALSE paths).
""",

    "text": """⚠️⚠️⚠️ CRITICAL: CONDITION TYPE DETECTION ⚠️⚠️⚠️

STEP A: CONDITION PATTERN ANALYSIS

Read the query carefully and look for these EXACT patterns:

PATTERN 1 - CNDN_DOM (Domino/Cascading Condition):
Keywords: "if not then", "else check if", "if fails", "first check...if not"
Meaning: CASCADING conditions where each condition depends on the previous one's failure.

Structure in Flow Sequence: #condition containeer may varies according to the user query
  ##Flow Sequence
   1. Trigger (TRG_DB)
   2. Start
   3. Domino Condition (CNDN_DOM) 
      ↳ Container 1 (CNDN_LGC_DOM)
         → IF: Check status is Low → Send Email (EVNT_NOTI_MAIL)
         → ELSE: Route to Container 2
      ↳ Container 2 (CNDN_LGC_DOM)
         → IF: Check status is Medium → Send Alert (EVNT_NOTI_NOTI)
         → ELSE: Route to END
   4. End

Examples that MUST use CNDN_DOM:
- "First check if X then A, if not then check if Y then B" → CNDN_DOM ✓
- "Check if status is Low then email, if not then check if status is Medium then alert" → CNDN_DOM ✓
- "Try X, if fails try Y, if fails try Z" → CNDN_DOM ✓

PATTERN 2 - CNDN_SEQ (Sequence/Parallel Condition):
Keywords: "AND check if", "and check if", "and verify if", "and if"
Meaning: INDEPENDENT parallel conditions that are ALL evaluated simultaneously.

Structure in Flow Sequence:
    ##Flow Sequence
   1. Trigger (TRG_DB)
   2. Start
   3. Sequence Condition (CNDN_SEQ)
      ↳ Logic Block 1 (CNDN_LGC): Check if status is approved → Send Email (EVNT_NOTI_MAIL)
      ↳ Logic Block 2 (CNDN_LGC): Check if amount > 1000 → Send Alert (EVNT_NOTI_NOTI)
   4. End

Examples that MUST use CNDN_SEQ:
- "Check if A then X, AND check if B then Y" → CNDN_SEQ ✓
- "Check if status is approved then send email, and check if amount > 1000 then send alert" → CNDN_SEQ ✓
- "Verify status AND verify amount AND verify date" → CNDN_SEQ ✓

PATTERN 3 - CNDN_BIN (Binary Condition):
Keywords: "if X then Y", "if X then Y else Z", "when X then Y"
Meaning: Single condition with two possible paths (TRUE/FALSE), no cascading, no parallel.

⚠️ CRITICAL: CNDN_BIN ELSE BRANCH SPECIFICATION
- Always explicitly specify BOTH branches in your workflow plan
- Structure must show what happens in BOTH IF TRUE and IF FALSE cases

Structure in Flow Sequence:( ALWAYS SHOW BOTH BRANCHES:)
   ##Flow Sequence
   1. Trigger (TRG_DB)
   2. Start
   3. Binary Condition (CNDN_BIN)
      ↳ IF TRUE: Send Email (EVNT_NOTI_MAIL) → END
      ↳ IF FALSE: Send Notification (EVNT_NOTI_NOTI) → END
   4. End

  CRITICAL RULES:
   - ALWAYS show both IF TRUE and IF FALSE paths
   - If no explicit ELSE action in query, write: "↳ IF FALSE: route to END"
   - Each branch MUST show the event code in parentheses: (EVNT_XXX)
   - Always include → END at the end of each branch path

Examples that MUST use CNDN_BIN:
- "If quantity > 100 send email, else send notification"
  → CNDN_BIN
  → IF TRUE: Send Email (EVNT_NOTI_MAIL)
  → IF FALSE: Send Notification (EVNT_NOTI_NOTI)

- "If status is active update record, else delete record"
  → CNDN_BIN
  → IF TRUE: Update Record (EVNT_RCRD_UPDT)
  → IF FALSE: Delete Record (EVNT_RCRD_DEL)

- "If user exists create record" (no else specified)
  → CNDN_BIN
  → IF TRUE: Create Record (EVNT_RCRD_ADD)
  → IF FALSE: do nothing (route to END)

- "Send email when status = approved" (implicit single-branch)
  → CNDN_BIN
  → IF TRUE: Send Email (EVNT_NOTI_MAIL)
  → IF FALSE: do nothing (route to END)

CRITICAL DISTINCTION TABLE:

| Query Pattern | Condition Type | Reason |
|--------------|----------------|--------|
| "if not then check" | CNDN_DOM | Cascading - second check only if first fails |
| "else check if" | CNDN_DOM | Cascading - each else leads to next check |
| "first check...if not" | CNDN_DOM | Cascading - sequential with fallback |
| "AND check if" | CNDN_SEQ | Parallel - all conditions evaluated independently |
| "and check if" | CNDN_SEQ | Parallel - all conditions evaluated independently |
| Single "if X then Y" | CNDN_BIN | Simple binary - one condition with implicit ELSE to END |
| "if X then Y else Z" | CNDN_BIN | Simple binary - one condition with explicit ELSE |
| Single "when X" | CNDN_BIN | Simple binary - one condition with implicit ELSE to END |


⚠️ CONDITION TYPE DECISION PROCESS:

STEP A: Count the conditions in the query
- How many "if" statements are there?
- How many "check if" statements are there?
- Are they connected by "and" or are they cascading with "if not/else"?

STEP B: Apply these rules:

CNDN_BIN (Binary Condition) - Use for SINGLE IF-THEN branching:
- ONE condition with IF-THEN-ELSE logic (explicit or implicit ELSE)
- Keywords: "if X then do Y", "if X then create else update", "when X then Y", "send email if X"
- ALWAYS specify in Flow Sequence:
  * What happens when TRUE
  * What happens when FALSE (even if it's "route to END")
- Examples:
  - "If value > 100 create a record" 
    → Flow: IF TRUE: Create, IF FALSE: END
  - "Send email if status is pending" 
    → Flow: IF TRUE: Send Email, IF FALSE: END
  - "If quantity < 50 then update record else delete record" 
    → Flow: IF TRUE: Update, IF FALSE: Delete

CNDN_SEQ (Sequence Condition) - Use for MULTIPLE INDEPENDENT parallel conditions:
- 2+ independent conditions, each with its own separate action
- Keywords: "check if A then X, AND check if B then Y", "verify if A AND verify if B"
- REQUIRES: "and check if" or "and if" connecting independent conditions
- Each condition is evaluated independently (parallel, not cascading)
- Contains CNDN_LGC (Logic Block) for each independent condition
- Examples:
  - "Check if status is approved then send email, AND check if amount > 1000 then send alert" 
    → CNDN_SEQ with 2 CNDN_LGC blocks
  - "Verify if user exists then log, AND verify if email is valid then proceed" 
    → CNDN_SEQ with 2 CNDN_LGC blocks

CNDN_DOM (Domino Condition) - Use for CASCADING sequential conditions:
- Conditions where each ELSE leads to the next condition check
- Keywords: "first check X, if not then check Y", "try X, if fails try Y"
- Each condition depends on previous condition's failure
- Examples:
  - "First check if user exists, if not then check permissions, if not then check quota" 
    → CNDN_DOM with 3 containers
  - "Try premium service, if fails try standard, if fails try basic" 
    → CNDN_DOM with 3 containers

DO NOT include ANY condition (CNDN_BIN, CNDN_SEQ, CNDN_DOM) for:
- Simple data extraction with filtering conditions (JMES/Filter handle conditions internally)
- Direct action events with built-in conditions (duplicate/restore/delete/update handle "where/when" conditions internally)
- Sequential actions without conditional branching ("do A then do B then do C")
- Examples:
  - "Get names where salary > 50000" → EVNT_JMES ONLY (no CNDN_BIN)
  - "Get records where status = 'active'" → EVNT_FLTR ONLY (no CNDN_BIN)
  - "duplicate the record where id = 5" → EVNT_RCRD_DUP ONLY (no CNDN_BIN)
  - "delete a record when status is expired" → EVNT_RCRD_DEL ONLY (no CNDN_BIN)
  - "Send email" → EVNT_NOTI_MAIL ONLY (no condition)
  - "Create a record" → EVNT_RCRD_ADD ONLY (no condition)

⚠️ CRITICAL DISTINCTION:
- "but X be Y" = Field specification (set X to Y) → NO condition needed
- "if X then Y" = Conditional branching (check X, decide action) → USE appropriate condition
- "then" connecting sequential actions = Simple sequence → NO condition needed
- "then" after "if" = Conditional branch → USE appropriate condition
- "where" in data queries = Filter criteria → NO condition needed (handled by event)
- "when" in direct actions (delete when, update when) = Built-in filter → NO condition needed

"""
}

PROMPT_LOOPS_TYPES = {

    "doc_type": "RULE",
    "topic": "loops",
    "priority": 70,
    "data": """ROUTER.RULE.loops
Intent: repetition / iteration in workflow.
Signals: repeat, times, for each, for every, loop, iterate, from X to Y, while, until, do while, break, continue.
Output: choose EVNT_LOOP_FOR / EVNT_LOOP_WHILE / EVNT_LOOP_DOWHILE (+ EVNT_LOOP_BREAK / EVNT_LOOP_CONTINUE if requested).
""",

    "text": """
3. Loop Events (EVNT_LOOP_FOR, EVNT_LOOP_WHILE, EVNT_LOOP_DOWHILE):

Use EVNT_LOOP_FOR when:
- Iterating over data collections: "for each item in", "for every record", "process all items"
- Iterating over numeric ranges: "loop from X to Y", "from 1 to 10", "repeat 5 times"

Use EVNT_LOOP_WHILE when:
- Condition checked BEFORE each iteration
- Keywords: "while X is true", "as long as", "until X becomes"

Use EVNT_LOOP_DOWHILE when:
- Action executes at least ONCE, then condition checked
- Keywords: "do X at least once", "execute then check"

Use EVNT_LOOP_BREAK when:
- Need to exit loop immediately based on condition
- Keywords: "break when", "exit loop if", "stop loop when"

Use EVNT_LOOP_CONTINUE when:
- Need to skip current iteration
- Keywords: "skip if", "continue to next if"

⚠️⚠️⚠️ CRITICAL: QUERY INTERPRETATION - WHEN TO USE LOOPS ⚠️⚠️⚠️

PATTERN 1: LOOP INSIDE CONDITION (Query has BOTH condition AND repetition)
Query pattern: "When [condition], [action] N times"
Examples:
- "When status is approved, send 10 emails"
- "If amount > 1000, create 5 records"
- "When user is active, notify 3 times"

Structure:
3. Binary Condition (CNDN_BIN)
   ↳ IF TRUE: For Loop (EVNT_LOOP_FOR)
      ↳ INSIDE LOOP: <Action> (<EVENT_CODE>)
   ↳ IF FALSE: Route to END
4. End

Flow visualization:
START → Binary Condition → IF TRUE → Loop → Loop Start → Action (inside loop) → Loop End → END
                        └→ IF FALSE → END

PATTERN 2: STANDALONE LOOP (Query has ONLY repetition, NO condition)
Query pattern: "[Action] N times" (no "when" or "if")
Examples:
- "Send email 10 times"
- "Create 5 records"
- "Loop through all items and update them"

Structure:
3. Loop Start (EVNT_LOOP_FOR)
   ↳ INSIDE LOOP: <Action> (<EVENT_CODE>)
4. Loop End
5. End

Flow visualization:
START → Loop Start → Action (inside loop) → Loop End → END

DECISION TREE - Which pattern to use?
1. Does query have condition keywords ("when", "if", "whenever")?
   YES → Check for repetition
         Has repetition ("N times", "repeat", "loop")? 
         YES → Use PATTERN 1 (Loop INSIDE condition)
         NO  → Use simple binary condition (no loop)
   NO  → Check for repetition
         Has repetition ("N times", "repeat", "loop")?
         YES → Use PATTERN 2 (Standalone loop)
         NO  → Use simple event (no condition, no loop)

⚠️⚠️⚠️ CRITICAL: UNIVERSAL FORMATTING RULES FOR BINARY CONDITIONS ⚠️⚠️⚠️

When ANY event appears inside a Binary Condition (CNDN_BIN) branch, follow these rules:

CORE PRINCIPLE:
- Events inside conditional branches are NOT numbered
- Events inside conditional branches use ↳ arrow notation
- Event codes MUST appear on the same line as the branch indicator (IF TRUE/IF FALSE)

STRUCTURE PATTERN FOR CONDITIONS:

## Flow Sequence
1. Trigger (...)
2. Start
3. Binary Condition (CNDN_BIN)
   ↳ IF TRUE: <Description> (<EVENT_CODE>)
      [↳ nested content if event has sub-items]
   ↳ IF FALSE: <Description> (<EVENT_CODE>) OR Route to END
4. End

STRUCTURE PATTERN FOR STANDALONE LOOPS:

## Flow Sequence
1. Trigger (...)
2. Start
3. Loop Start (<EVNT_LOOP_XXX>)
   ↳ INSIDE LOOP: <Action> (<EVENT_CODE>)
4. Loop End
5. End

FORMATTING RULES:

Rule 1: BRANCH EVENT PLACEMENT (For conditions)
✅ Correct: ↳ IF TRUE: <Action Description> (<EVENT_CODE>)
❌ Wrong:   ↳ IF TRUE: <Some text> → 
            4. <Action Description> (<EVENT_CODE>)

Rule 2: NUMBERING
- Only number: Trigger, Start, top-level Conditions/Events/Loops, Loop End, End
- Never number: Anything inside a conditional branch
- Never number: Anything inside a loop (use ↳ INSIDE LOOP)
- Inside branches: Use ↳ exclusively

Rule 3: EVENT CODE INCLUSION
- ALWAYS include event codes in parentheses: (EVNT_XXX)
- Event code appears on the SAME LINE as the branch (IF TRUE/IF FALSE)
- If branch has multiple events, repeat the branch indicator for each

Rule 4: BRANCH COMPLETENESS (For conditions)
- ALWAYS specify both IF TRUE and IF FALSE
- If a branch has no action: write "Route to END"

Rule 5: NESTED CONTENT (For loops)
- Loop internals ALWAYS use "INSIDE LOOP:" prefix
- Use ↳ indentation for items inside loops
- Never number items inside loops

Rule 6: MULTIPLE EVENTS IN ONE BRANCH
- Repeat the branch indicator (↳ IF TRUE or ↳ IF FALSE) for each event
- Each event gets its own line with its event code

COMPLETE EXAMPLES:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Example 1: Loop INSIDE condition (PATTERN 1)
Query: "When application status changes to Approved, send 10 times email notifications to anish@gmail.com"

## Flow Sequence
1. Trigger (TRG_DB)
2. Start
3. Binary Condition (CNDN_BIN)
   ↳ IF TRUE: For Loop (EVNT_LOOP_FOR)
      ↳ INSIDE LOOP: Send Email Notification (EVNT_NOTI_MAIL)
   ↳ IF FALSE: Route to END
4. End

Why this structure:
- Query has condition: "When status changes to Approved" → Binary Condition needed
- Query has repetition: "send 10 times" → Loop needed
- Both present → Loop goes INSIDE the IF TRUE branch
- Email event goes INSIDE the loop
- No numbered items inside the condition
- No numbered items inside the loop

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Example 2: Standalone loop (PATTERN 2)
Query: "Send email to anish@gmail.com 10 times"

## Flow Sequence
1. Trigger (TRG_DB)
2. Start
3. Loop Start (EVNT_LOOP_FOR)
   ↳ INSIDE LOOP: Send Email (EVNT_NOTI_MAIL)
4. Loop End
5. End

Why this structure:
- Query has NO condition (no "when", "if")
- Query has repetition: "10 times" → Loop needed
- No condition → Loop is standalone (numbered as step 3)
- Email event goes INSIDE the loop
- Loop End is numbered (step 4)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Example 3: Condition WITHOUT loop
Query: "When status is approved, send email to anish@gmail.com"

## Flow Sequence
1. Trigger (TRG_DB)
2. Start
3. Binary Condition (CNDN_BIN)
   ↳ IF TRUE: Send Email (EVNT_NOTI_MAIL)
   ↳ IF FALSE: Route to END
4. End

Why this structure:
- Query has condition: "When status is approved" → Binary Condition needed
- Query has NO repetition (no "N times") → No loop needed
- Email event goes directly in IF TRUE branch

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Example 4: Multiple events in loop inside condition
Query: "When quantity > 100, loop 5 times and create record then send email each time"

## Flow Sequence
1. Trigger (TRG_DB)
2. Start
3. Binary Condition (CNDN_BIN)
   ↳ IF TRUE: For Loop (EVNT_LOOP_FOR)
      ↳ INSIDE LOOP: Create Record (EVNT_RCRD_ADD)
      ↳ INSIDE LOOP: Send Email (EVNT_NOTI_MAIL)
   ↳ IF FALSE: Route to END
4. End

Why this structure:
- Condition + repetition → Loop inside IF TRUE
- Multiple actions per iteration → Multiple "INSIDE LOOP" items
- Both events execute on each loop iteration

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Example 5: Nested loops (loop inside loop) - standalone
Query: "Loop 3 times, and in each iteration loop 5 times to send email"

## Flow Sequence
1. Trigger (TRG_DB)
2. Start
3. Outer Loop Start (EVNT_LOOP_FOR)
   ↳ INSIDE LOOP: Inner Loop Start (EVNT_LOOP_FOR)
      ↳ INSIDE LOOP: Send Email (EVNT_NOTI_MAIL)
4. Outer Loop End
5. End

Why this structure:
- No condition → Standalone loops
- Nested loops → Inner loop is INSIDE outer loop
- Email is INSIDE the inner loop

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

WRONG PATTERNS - NEVER DO THESE:

❌ WRONG Pattern 1: Loop as separate numbered step after condition
3. Binary Condition (CNDN_BIN)
   ↳ IF TRUE: Send Email (EVNT_NOTI_MAIL)
   ↳ IF FALSE: Route to END
4. Loop Start (EVNT_LOOP_FOR)
   ↳ INSIDE LOOP: Send Email (EVNT_NOTI_MAIL)

Why wrong: Loop executes AFTER condition completes, not inside IF TRUE

❌ WRONG Pattern 2: Numbered items inside condition
3. Binary Condition (CNDN_BIN)
   ↳ IF TRUE: Loop Started
   4. Loop (EVNT_LOOP_FOR)
      ↳ INSIDE LOOP: Send Email (EVNT_NOTI_MAIL)

Why wrong: Cannot number items inside a conditional branch

❌ WRONG Pattern 3: Event before loop in same branch
3. Binary Condition (CNDN_BIN)
   ↳ IF TRUE: Send Email (EVNT_NOTI_MAIL)
   ↳ IF TRUE: For Loop (EVNT_LOOP_FOR)
      ↳ INSIDE LOOP: Send Email (EVNT_NOTI_MAIL)

Why wrong: If query says "send N times", there should be ONLY the loop, not a separate email before it

APPLICABILITY:
These rules apply to ALL event types:
- Loops (EVNT_LOOP_*)
- Notifications (EVNT_NOTI_*)
- Record operations (EVNT_RCRD_*)
- User management (EVNT_USER_*)
- Formulas (EVNT_FRMLA_*)
- Static record operations (EVNT_STC_RCRD_*)
- Any other event type

CRITICAL DON'TS:
❌ DO NOT create numbered items inside conditional branches
❌ DO NOT create numbered items inside loops
❌ DO NOT put event codes on separate lines from branch indicators
❌ DO NOT omit the IF FALSE branch (always specify it)
❌ DO NOT use → for flow continuation within branches (use ↳ only)
❌ DO NOT mix numbered and ↳ notation within the same conditional block

CRITICAL DO's:
✅ DO use ↳ for all items inside conditional branches
✅ DO use ↳ for all items inside loops with "INSIDE LOOP:" prefix
✅ DO include event code on same line as IF TRUE/IF FALSE
✅ DO specify both branches (IF TRUE and IF FALSE)
✅ DO use "Route to END" for branches with no action
✅ DO nest sub-items with additional ↳ indentation
✅ DO number only top-level flow steps (Trigger, Start, Condition, Loop Start, Loop End, End)
✅ DO mark loop internals with "INSIDE LOOP:"

LOOP TYPE IDENTIFICATION:
- DATA ITERATION LOOP: "for each item in", "for every record", "process all items", "each record"
- RANGE ITERATION LOOP: "from X to Y", "loop from A to B", "1 to 10", "repeat N times", "send X times"
```
"""
}



PROMPT_DATA_OPS_RULES = {

    "doc_type": "RULE",
    "topic": "data_ops_rules",
    "priority": 80,
    "data": """ROUTER.RULE.data_ops_rules
Intent: compute/transform/derive a value or reshape data.
Signals: calculate, compute, sum, total, percentage, concat, uppercase/lowercase, split, replace, regex, format date, add days, round, uuid, random.
Output: use EVNT_DATA_OPR.""",

    "text": """TEP X: Formula / Calculation Detection (EVNT_DATA_OPR)
Use EVNT_DATA_OPR when the user wants to:
- Perform any calculation: add, subtract, multiply, divide, power, percentage, etc.
- Manipulate strings: uppercase, lowercase, concatenate, extract, replace, split, regex
- Work with dates: format, add/subtract days, get weekday, convert timezone
- Generate random values, UUIDs, sequences
- Derive/compute a field value before creating/updating a record
- Clean/format data (trim, round, type conversion)
- Complex conditional value assignment that goes beyond simple field mapping

Keywords/phrases that trigger EVNT_DATA_OPR:
"calculate", "compute", "add ... and ...", "subtract", "multiply", "divide", "total", "sum", "difference",
"uppercase", "lowercase", "capitalize", "concatenate", "join", "split", "extract", "replace",
"format date", "add days", "current date", "today + 7", "weekday", "convert timezone",
"round", "absolute", "generate random", "if ... then ... else" (for value assignment, not branching)

Examples – ALWAYS use EVNT_DATA_OPR:
- "create a record where full_name is first_name + last_name" → EVNT_DATA_OPR (concat) + EVNT_RCRD_ADD
- "set expiry_date to today + 30 days" → EVNT_DATA_OPR (add_timedelta) + EVNT_RCRD_ADD/_UPDT
- "calculate total_amount = quantity * price" → EVNT_DATA_OPR
- "make email lowercase before saving" → EVNT_DATA_OPR (lower)
- "extract phone number using regex" → EVNT_DATA_OPR (findall/sub)
- "generate a random 8-digit OTP" → EVNT_DATA_OPR
- "set status to 'Overdue' if due_date < today" → EVNT_DATA_OPR + CNDN_BIN if branching needed

DO NOT use CNDN_BIN just for value assignment – use EVNT_DATA_OPR for computed fields.
Only use CNDN_BIN when the entire action branches (e.g., create vs update, send email or not).

The workflow plan is NOT JSON.
It should describe:
- Workflow name & description
- Trigger details (type code)
- Events & actions (event codes, purpose)
- Conditions / logic steps (include ONLY for conditional actions, not data filtering)
- Flow sequence (ordered steps from trigger to end)

Stick strictly to the user's request. Do not add extra actions, events, or features such as notifications, emails, or any other outputs unless explicitly mentioned in the query. For example, if the user asks to retrieve or filter records, do not add sending notifications.

"""
}

PROMPT_TRIGGERS_CATALOG = {

    "doc_type": "CATALOG",
    "topic": "triggers_catalog",
    "priority": 40,
    "data": """
Trigger Type Selection (TRG_DB / TRG_API / TRG_FILE / TRG_SCH / TRG_BTN / TRG_WBH / TRG_AUTH / TRG_APRVL / TRG_FLD / TRG_OUT)
Use this when a query needs the correct workflow trigger. Maps user intent to trigger type: database record changes → TRG_DB, API calls → TRG_API, file upload/import → TRG_FILE, scheduled/time-based → TRG_SCH, button/UI click → TRG_BTN, incoming webhook → TRG_WBH, auth events (login/logout/password reset/change) → TRG_AUTH, approval actions → TRG_APRVL, field entry/update in UI → TRG_FLD, and timeouts/expiry → TRG_OUT.
""",

    "text": """
TRIGGERS LIST
TRG_API = "API Trigger"
TRG_DB = "Database Trigger"
TRG_FILE = "File Trigger"
TRG_SCH = "Scheduled Trigger"
TRG_BTN = "UI Trigger"
TRG_WBH = "Webhook Trigger"
TRG_AUTH = "Authentication Trigger"
TRG_APRVL = "UI Approval Trigger"
TRG_FLD = "UI Field Entry Trigger"
TRG_OUT = "Process Timeout Trigger"

TRIGGER METHODS
["pwd_reset","login","logout","cng_pwd","add_helpdesk","mod_helpdesk","delete_helpdesk",
"restore_helpdesk","add_form","mod_form","del_form","add_record","mod_record",
"restore_record","del_record","add_user","del_user","mod_user","restore_user",
"approved_public_registration","rejected_public_registration","add_department","mod_department",
"del_department","restore_department","add_role","mod_role","delete_role","restore_role",
"{method.lower()}_{str(status_code).lower()}"]

"""
}

PROMPT_PLANNER_POLICY = {

    "doc_type": "RULE",
    "topic": "planner_policy",
    "priority": 80,
    "data": """
ROUTER.RULE.planner_policy
Intent: output format + plan writing constraints (Markdown sections, omit unused sections, flow numbering, branch formatting).
Output: formatting policy only (not event selection).
""",

    "text": """
CONDITIONS LIST WITH DESCRIPTIONS
Include conditions ONLY if the workflow requires separate logical checks beyond inherent event logic (e.g., do not include for simple filters where the filter event already handles the criteria). Examples:
- Field value comparisons with branching: if quantity > 100 then X, else Y
- Boolean logic with branching: AND, OR, NOT
- Range checks with branching: if 10 <= age <= 50 then X

NEVER include CRUD actions (add_record, mod_record, delete_record, etc.) in conditions.
If no separate logical conditions are required, skip the Conditions section entirely.

CNDN_BIN = "Binary Condition - Binary Conditions in Workflow Management trigger actions based on true/false logic evaluations. A basic setup includes a logic block, an If block for true actions, and an Else block for false actions. Complex conditions can combine multiple criteria using AND/OR operators. Always validate and test conditions to ensure workflows run as expected."

CNDN_SEQ = "Sequential Condition - Sequential Conditions let you run logical checks in a set order, executing the first matching condition's action and skipping the rest. A basic setup handles simple scenarios, while complex setups use logical operators for multi-criteria conditions. Always validate and test to ensure correct actions trigger based on different sequential checks. Use with CNDN_LGC for each independent logic block."

CNDN_LGC = "Logic Block - Used within CNDN_SEQ to represent individual independent condition checks. Each CNDN_LGC contains one condition and its associated action."

CNDN_DOM = "Domino Condition - Domino Conditions enable sequential logical evaluations in workflows, triggering specific actions in order until a match is found, with fallback options for unmatched scenarios. A basic setup defines multiple conditions with corresponding actions, while complex conditions use logical operators (AND/OR) for advanced logic. Always validate and test conditions to ensure accurate execution across all scenarios."

CNDN_LGC_DOM = "Logic Domino Condition - Advanced domino conditions using logical operators (AND/OR) for complex multi-criteria evaluations in sequential order."

IMPORTANT INSTRUCTIONS:
- Analyze the user request thoroughly to identify all required components
- Create a comprehensive workflow plan that includes all necessary events, conditions, and loops
- Use appropriate triggers based on the request context
- Include conditions only when separate logical checks with branching are needed beyond event-inherent logic
- Use loops when repetitive actions are required (for each, loop from X to Y, etc.)
- Structure the workflow in a logical sequence from trigger to completion
- Make sure to use the correct event codes and descriptions
- Do not infer or add any extra steps, such as notifications or additional actions, unless explicitly stated in the user request
- For loops, mark events inside the loop with "(INSIDE LOOP)" notation
- For CNDN_SEQ, include CNDN_LGC for each independent logic block

Examples:

Simple action workflow (no conditions):
- Trigger: Database add_record
- Action: Send email notification
- No Conditions section included

Conditional workflow (CNDN_BIN - single condition):
- Trigger: Database update_record
- Condition: if status == "approved" then send email, else do nothing
- Action: Send email notification

Multiple independent conditions (CNDN_SEQ with CNDN_LGC):
- Trigger: Database add_record  
- Condition: CNDN_SEQ containing:
- CNDN_LGC: Check if risk = High then alert
- CNDN_LGC: Check if type = Permit then assign
- Actions: Send alert, Assign to team

Cascading conditions (CNDN_DOM):
- Trigger: API call
- Condition: CNDN_DOM - First check user exists, if not check permissions, if not check quota
- Actions: Based on which condition matches

Loop workflow:
- Trigger: File upload
- For Loop: Process each record in the file (EVNT_LOOP_FOR - data_iteration_loop)
- Action: Create record for each item (INSIDE LOOP)

Range Loop workflow:
- Trigger: UI Button click
- For Loop: Loop from 1 to 10 (EVNT_LOOP_FOR - range_iteration_loop)
- Action: Send email (INSIDE LOOP)

Filter workflow (no separate conditions or extra actions):
- Trigger: Database mod_record
- Action: Filter records where quantity > 90
- No Conditions section, no notifications

OUTPUT: Markdown Structured Workflow Plan ONLY.
- Include the Conditions / logic steps section only if applicable (actual branching logic needed).
- If the workflow is a simple action (e.g., add record, send email, SMS, push) or simple filter/retrieve, omit the Conditions section.
- Include loops when repetitive processing is needed.
- Mark loop internal events with "(INSIDE LOOP)" notation.
- For CNDN_SEQ, show each CNDN_LGC logic block.
"""
}

PROMPT_NOTIFICATIONS_INTENT = {
    "doc_type": "RULE",
    "topic": "notifications_intent",
    "priority": 95,
    "data": """
ROUTER.RULE.notifications_intent
Intent: send a message/notification to a recipient.
Signals: email, mail, notify, notification, alert, sms, text message, push, webhook.
Output: select EVNT_NOTI_* event family (exact mapping handled by agent/backstory).
""",
    "text": """Use when the user request is primarily about sending a notification/message.
Do not use for record CRUD, loops, or computations."""
}



chunk_data = [
    PROMPT_ACTION_EVENTS_BUILTIN_FILTERING,
    PROMPT_NOTIFICATIONS_INTENT,
    PROMPT_DATA_OPS_RULES,
    PROMPT_COND_OVERVIEW_AND_PATTERNS,
    PROMPT_LOOPS_TYPES,
    PROMPT_PLANNER_POLICY,
]

