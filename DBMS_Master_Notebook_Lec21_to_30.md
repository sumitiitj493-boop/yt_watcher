# DBMS Master Notebook
## Lectures 21–30 · ER Advanced + Functional Dependency + Normalization (1NF → BCNF)

> Personal coaching notebook — not a dump of the transcript.
> Sequence here is **conceptual**, not video-number order:
> **Weak Entity → ER-to-tables (GATE) → Why Normalize → 1NF → FD → Closure → 2NF → 3NF → BCNF.**
>
> Source lectures: Gate Smashers / Dbms3 · Lec 21, 22, 23, 24, 25, 26, 27, 28, 29, 30.

---

### How to use this notebook

1. First pass: read **Intuition → Why → Example → Exam-ready**.
2. Second pass: redo every worked example with a blank page.
3. Night before exam: only **Part E · Quick Revision & Exam Radar**.

---

# Conceptual tree (yeh chapters alag nahi hain)

```
ER Model
 ├─ Strong entity  ──has──► Primary key
 ├─ Weak entity    ──needs─► Owner PK + partial key
 └─ Relationships  ──convert──► tables
        1:1  → merge possible
        1:N  → FK on MANY side   (R table droppable)
        M:N  → MUST keep relationship table

Why split tables?  → Insertion / Deletion / Updation anomalies
How to split safely? → Normalization using Functional Dependencies

FD  X → Y          “X determines Y”
Closure X⁺         “what can X find?”
Candidate keys     from closures that cover ALL attributes
Prime / Non-prime  from the set of ALL candidate keys

1NF  atomic cells
2NF  1NF + no partial dependency     (proper-subset-of-CK → non-prime)
3NF  2NF + no bad transitive dep     (X superkey  OR  A prime)
BCNF every determinant is a superkey (the OR of 3NF is deleted)
```

---

# PART A — ER ADVANCED
## Lec 21 · Weak Entity Set

### 1. Intuition

A **strong entity** is a person with their own Aadhaar.
A **weak entity** is a dependent who the company does **not** give an independent ID.

Infosys stores employees with unique `EID`.
It may also store an employee’s spouse / child for a policy.
Infosys will **never** mint a new company-ID for that spouse.
If the employee leaves, the dependent record is meaningless.

Simple bhasha me: *weak entity khud se pehchan nahi kar sakti. Owner ke bina uska existence hi nahi.*

### 2. Technical definition

A **weak entity set** is an entity set that has **no primary key of its own**.
It is identified only through an **owner (identifying) entity set** plus its own **partial key (discriminator)**.

It has **existence dependency** on the owner: it participates **totally** in the **identifying relationship**.

### 3. Why?

Primary key = unique + not null.
If no such attribute exists inside the entity, rows cannot be distinguished by that entity alone.
So the model borrows uniqueness from the owner.

### 4. Chen notation (must-write in diagrams)

| Thing | Symbol |
|---|---|
| Strong entity | Single rectangle |
| Weak entity | **Double rectangle** |
| Ordinary relationship | Single diamond |
| Identifying relationship | **Double diamond** |
| Primary key | **Solid underline** |
| Partial key / discriminator | **Dotted / dashed underline** |
| Total participation | **Double line** from entity to relationship |
| Partial participation | Single line |

![Figure A.1 Weak entity Chen diagram](images/01_weak_entity_er.png)

**Figure A.1 — Weak entity set in Chen notation.** Employee is the owner. Dependent is weak. `HAS` is the identifying relationship. `Name` is only a partial key.

### 5. Running example — Employee / Dependent

Company data:

| EID (PK) | EName | Address |
|---|---|---|
| E1 | Varun | Chandigarh |
| E2 | Ravi | Delhi |
| E3 | Amrit | Mumbai |

Dependents (no company ID):

| Name | Age | belongs to |
|---|---|---|
| A | 16 | E1 |
| B | 17 | E1 |
| A | 16 | E2 |

Two different employees can have a child named **A**, even of the same age.
`Name` is **not** unique in the company. It is only *somewhat* distinguishing **inside one employee**. That is why it is a **partial key**, not a primary key.

- Employee **E3** may have **zero** dependents → owner participation is **partial**.
- Every dependent row exists **only because** some employee exists → weak side is **total**.

> **Yaad rakhna**
> Weak side = always total participation in the identifying relationship.
> Owner side = usually partial (some owners have no weak children).

### 6. Conversion to relational tables

Naive student writes **3 tables**: Employee, HAS, Dependent.
That is wrong for a weak entity.

Dependent **cannot live alone** (no PK). The identifying relationship is also not an independent M:N story here. We **merge** weak entity + identifying relationship.

**Minimum = 2 tables.**

```text
Employee ( EID, EName, Address )
           ───
           PK

HasDependent ( EID, Name, Age )
               ───  ────
               FK → Employee.EID
               PK = (EID, Name)     ← composite
```

```sql
CREATE TABLE Employee (
    EID     INT PRIMARY KEY,
    EName   VARCHAR(50),
    Address VARCHAR(100)
);

CREATE TABLE HasDependent (
    EID  INT,
    Name VARCHAR(50),
    Age  INT,
    PRIMARY KEY (EID, Name),          -- owner PK + partial key
    FOREIGN KEY (EID) REFERENCES Employee(EID)
        ON DELETE CASCADE             -- existence dependency
);
```

Why `(EID, Name)` and not `EID` alone?
One employee can have many dependents → `EID` repeats.
Why not `Name` alone?
Two employees can have the same dependent-name.

> **Galti se bhi mat bhoolna**
> In the ER diagram, `Name` is a **partial key** (dotted underline).
> After conversion, the table’s primary key is **composite**: owner PK + partial key.

### 7. Important properties

1. Weak entity has **no** primary key of its own.
2. It is identified by **owner PK + partial key**.
3. Identifying relationship = **double diamond**.
4. Weak entity = **double rectangle**.
5. Partial key = **dotted underline**.
6. Weak entity has **total** participation (existence dependency).
7. On conversion: **do not** create a standalone weak table; merge with the identifying relationship.
8. Typical cardinality: owner : weak = **1 : N**.

### 8. Common traps

| Trap | Truth |
|---|---|
| “Weak entity has no key at all.” | It has a **partial** key. After mapping it has a **composite PK**. |
| “Owner must also participate totally.” | **No.** Owner is usually partial. |
| “Always 3 tables (entity + rel + entity).” | Weak + identifying rel **merge**. Usually **2**. |
| “Partial key is underlined solid.” | Solid = primary. Partial = **dotted**. 1-mark favourite. |

> **Interviewer / examiner yahan phansayega**
> “Must the *owner* have total participation?”
> Answer: **No.** The **weak** entity must. GATE-style wording: *The weak entity set MUST have total participation in the identifying relationship.*

### 9. Exam-ready answer

> A weak entity set does not possess a primary key of its own. It is existence-dependent on an identifying owner entity and is distinguished by a partial key (discriminator). It is drawn as a double rectangle; the identifying relationship as a double diamond; the partial key with a dashed underline. In the relational mapping the weak entity is merged with its identifying relationship. The resulting table has primary key = (owner primary key + partial key) and a foreign key referencing the owner.

### 10. Memory hook

**Weak = double everything that identifies it**
double rectangle, double diamond, double line (total), and finally a **double-part PK**.

### 11. Quick check

Can two weak entities of *different* owners share the same partial-key value?
**Yes.** That is exactly why the owner PK must be part of the weak table’s primary key.

---

## Lec 22 · ER → Relational · Minimum tables
### Worked: GATE CSE 2005 Q.75

### 1. Intuition

ER is the **blueprint**.
Relational model is the **actual tables**.
Naive count = one table per entity + one table per relationship.
Minimum count = after **legal merges**.

### 2. Conversion rules (write these, not the picture)

![Figure A.2 ER to table rules](images/02_er_to_tables_rules.png)

**Figure A.2 — Minimum-table rules.** Pictures help memory; the table below is the mark-scoring version.

| Relationship | Participation (usual GATE default = partial if unstated) | Minimum tables for **two** strong entities + this relationship |
|---|---|---|
| **1 : 1** | both partial | **2** (FK on either side) |
| **1 : 1** | one side total | **1** possible (merge into the total side) |
| **1 : N** | both partial | **2** (put ONE-side PK as FK on the **MANY** side) |
| **1 : N** | many-side total | still **2** typically; FK on many side is NOT NULL |
| **M : N** | any | **3** (relationship **must** be its own table) |
| **Weak + identifying 1:N** | weak total | owner table + **merged** weak table = **2** |
| **Multivalued attribute** | — | **+1 extra table** always |

**Where does the foreign key sit in 1:N?**
Always on the **N (many)** side.
One department has many employees → `Employee.Dno` references `Department`.

**What is the PK of a standalone 1:N relationship table?**
The PK of the **many** side (each many-entity occurs in at most one relationship instance).

**What is the PK of an M:N relationship table?**
**Composite** of both entity PKs (plus relationship attributes if any).

> **One-line memory hook**
> *1:N ka rista many-side ke pocket mein FK ban ke ghus jaata hai.
> M:N ko apna alag ghar (table) chahiye.*

### 3. Official GATE question (this one *was* asked)

**GATE CSE 2005 · Q.75**

> Let \(E_1\) and \(E_2\) be two entities in an E/R diagram with simple-valued attributes. \(R_1\) and \(R_2\) are two relationships between \(E_1\) and \(E_2\), where \(R_1\) is one-to-many and \(R_2\) is many-to-many. \(R_1\) and \(R_2\) do not have any attributes of their own. What is the minimum number of tables required to represent this situation in the relational model?
>
> (A) 2 &nbsp;&nbsp; (B) 3 &nbsp;&nbsp; (C) 4 &nbsp;&nbsp; (D) 5

![Figure A.3 GATE 2005 dual relationship](images/03_gate2005_er.png)

**Figure A.3 — Two relationships between the same pair of entities.** Only \(R_2\) (M:N) forces a third table.

### 4. Solution (do not jump)

**Given**
- Two strong entities, simple single-valued attributes (so no extra table for multivalued attributes).
- \(R_1\) is 1:N, no attributes of its own.
- \(R_2\) is M:N, no attributes of its own.
- Participation not stated → treat as **partial**.

**Naive count = 4**
`E1`, `E2`, `R1`, `R2`.
4 is an option — examiner trap.

**Reduce \(R_1\) (1:N)**

Let `E1.A` be PK of \(E_1\), `E2.B` be PK of \(E_2\).
Assume \(R_1\) is \(E_1(1)\) — \(E_2(N)\) as in the lecture (one \(E_1\) related to many \(E_2\)).

Standalone \(R_1\) would be:

```text
R1 ( A, B )     PK = B     (many-side key)
```

`E2` already has PK `B`.
**Same primary key ⇒ merge \(R_1\) into \(E_2\).**
`E2` becomes `E2(B, …, A)` with `A` as FK to `E1`.

This is the standard 1:N rule: **FK on the many side**.

**Cannot reduce \(R_2\) (M:N)**

Standalone \(R_2\):

```text
R2 ( A, B )     PK = (A, B)
```

`(A, B)` is **not** equal to `E1`’s PK, and **not** equal to `E2`’s PK.
Cannot merge into `E1`. Cannot merge into `E2`.
M:N **always** keeps its own table.

**Final minimum schema**

```text
T1 :  E1 ( A , … )                 PK = A
T2 :  E2 ( B , A , … )             PK = B ,  A is FK for R1
T3 :  R2 ( A , B )                 PK = (A, B) , both FKs
```

**Answer: 3  → option (B).**

### 5. Why the lecture’s “same PK ⇒ merge” line is correct

If two relations have the **same primary key**, they describe the **same object**.
Keeping both is redundant; a lossless join on that key rebuilds them.
That is the reduction used for 1:N (and for 1:1).

### 6. Traps on this exact question

- Counting 4 because “two relationships ⇒ two extra tables”.
- Trying to merge M:N into one entity (you will either lose combinations or create a multivalued attribute, which **breaks 1NF**).
- Forgetting that the question asks **minimum**, so 1:N **must** be merged.
- Adding a 4th table “to avoid NULLs”. For *minimum* GATE count, NULLs on a partial 1:N FK are accepted. (Some textbooks prefer a separate R table to avoid NULLs; that is **not** what this MCQ awards.)

### 7. Exam-ready 3-mark write-up

> \(E_1\) and \(E_2\) need two tables. \(R_1\) is 1:N, so the primary key of the one-side is placed as a foreign key in the many-side table; \(R_1\) does not need a separate table. \(R_2\) is M:N, so it must be a separate table with composite primary key \((PK(E_1), PK(E_2))\). Hence minimum tables = 3.

### 8. Quick check

If **both** \(R_1\) and \(R_2\) were M:N, minimum tables = ?
**4** (`E1`, `E2`, `R1`, `R2`). No merge is legal.

---

## Lec 23 · Participation + Cardinality
### Worked: GATE CSE 2018 Q.11

The lecture audio is badly broken. The **actual** GATE 2018 question (this *was* asked) is the one that matches the surviving phrases *“participate totally”*, *“associated with exactly one”*, *E1/E2*.

### Official statement

**GATE CSE 2018 · Q.11**

> In an Entity-Relationship (ER) model, suppose \(R\) is a many-to-one relationship from entity set \(E_1\) to entity set \(E_2\). Assume that \(E_1\) and \(E_2\) participate **totally** in \(R\) and that the **cardinality of \(E_1\) is greater than** the cardinality of \(E_2\).
>
> Which one of the following is true about \(R\)?
>
> (A) Every entity in \(E_1\) is associated with **exactly one** entity in \(E_2\)
> (B) Some entity in \(E_1\) is associated with **more than one** entity in \(E_2\)
> (C) Every entity in \(E_2\) is associated with **exactly one** entity in \(E_1\)
> (D) Every entity in \(E_2\) is associated with **at most one** entity in \(E_1\)

![Figure A.4 Many-to-one with total participation](images/04_gate2018_m_to_1.png)

**Figure A.4 — M:1 from E1 to E2, both sides total, |E1| > |E2|.** Each left entity has exactly one arrow. Right entities may have many incoming arrows. Both sides are covered.

### Decode the three given facts

| Phrase | Meaning |
|---|---|
| \(R\) is **many-to-one from \(E_1\) to \(E_2\)** | Each \(E_1\) entity relates to **at most one** \(E_2\). One \(E_2\) may relate to **many** \(E_1\). |
| \(E_1\) participates **totally** | Each \(E_1\) relates to **at least one** \(E_2\). Combined with M:1 → **exactly one**. |
| \(E_2\) participates **totally** | Each \(E_2\) relates to **at least one** \(E_1\). Combined with M:1 → **one or more**. |
| \(\lvert E_1\rvert > \lvert E_2\rvert\) | There are more left entities than right. Together with both-total + M:1, the mapping is a **surjective (onto)** many-to-one function \(E_1 \to E_2\). |

> **Yaad rakhna — two different “cardinalities”**
> 1. Cardinality **ratio** of a relationship: 1:1 / 1:N / M:N.
> 2. Cardinality **of a set**: how many entities are in that set.
>
> In this question, “cardinality of \(E_1\)” means **|E1|**, the number of entities.

### Option autopsy

| Opt | Claim | Verdict | Why |
|---|---|---|---|
| A | Every \(E_1\) ↔ **exactly one** \(E_2\) | **TRUE** | M:1 ⇒ at most one. Total \(E_1\) ⇒ at least one. |
| B | Some \(E_1\) ↔ **more than one** \(E_2\) | FALSE | That is M:N, forbidden by M:1. |
| C | Every \(E_2\) ↔ **exactly one** \(E_1\) | FALSE | M:1 allows many \(E_1\) per \(E_2\). Also \(\lvert E_1\rvert > \lvert E_2\rvert\) **forces** some \(E_2\) to have **more than one** \(E_1\). |
| D | Every \(E_2\) ↔ **at most one** \(E_1\) | FALSE | That would be 1:1 (from \(E_2\)’s view). Contradicts M:1 and \(\lvert E_1\rvert > \lvert E_2\rvert\). |

**Answer: (A).**

Real-life anchor: many **students** (\(E_1\)) mapped to one **mentor** (\(E_2\)). Every student has exactly one mentor (total + M:1). A mentor can have many students. If every mentor is used (total on \(E_2\)) and there are more students than mentors, at least one mentor has more than one student.

### Continuity

This is the same 1:N / M:1 merge rule as Lec 22:
because every \(E_1\) has **exactly one** \(E_2\), you can store `E2_key` as a **NOT NULL FK** inside the \(E_1\) table. With **both** sides total and M:1, some designs even merge into **one** table — but that was **not** asked here.

---

# PART B — WHY NORMALIZE, THEN THE TOOLS
## Lec 24 · Introduction to Normalization & Anomalies

### 1. Intuition

Awards ceremony ke ek register mein student + course + faculty + salary sab ek hi line mein likh do.
Same faculty ki salary 200 jagah repeat hogi.
Ab salary badhao — 200 jagah likhni padegi. Ek jagah bhool gaye to database jhoot bolne lagega.

**Normalization** = a rule-based way to **remove or reduce redundancy** so that insert / delete / update do not create contradictions.

### 2. Technical definition

Normalization is the process of decomposing relations by analyzing functional dependencies so that redundancy and update anomalies are reduced, while (ideally) keeping the decomposition **lossless** and **dependency-preserving**.

It does **not** always delete every repeated value. It deletes *harmful* repetition — repetition that is not controlled by a key.

### 3. Two kinds of duplication

| Kind | What it looks like | Cure |
|---|---|---|
| **Row-level** | Two tuples identical | **Primary key** (UNIQUE + NOT NULL) |
| **Column-level** | The same fact (F1’s salary = 30000) stored in many rows that are otherwise different | **Normalization** (split tables) |

Row-level is already killed by entity integrity (Lec 21–22 world).
Normalization exists mainly for **column-level** redundancy.

### 4. The three anomalies

Database has essentially three user operations after design: **insert, delete, update**.
Each can go wrong in a fat mixed table.

![Figure B.1 Three anomalies](images/05_three_anomalies.png)

**Figure B.1 — Insertion, deletion, updation anomalies.** One mixed table, three ways to get hurt. Split by subject and the same operations become safe.

Take a university table:

```text
STUDENT_COURSE_FACULTY
( SID, SName, CID, CName, FID, FName, Salary )
PK = SID     (lecture’s running assumption)
```

Imagine SID=2 is the **only** student in course C7 taught by F1.

#### Insertion anomaly

A new course `C10 / MBBS` is launched. No student has registered yet.
You cannot insert `(NULL, NULL, C10, MBBS, …)` because `SID` is primary key → **NOT NULL**.
Dummy SIDs are a crime scene, not a design.

Same story for a newly hired faculty with no assigned student.

#### Deletion anomaly

```sql
DELETE FROM StudentCourseFaculty WHERE SID = 2;
```

You wanted to remove **one student**.
You also destroyed the **only** copy of course C7 and faculty F1.
Information that is still true in the real world is gone.

#### Updation anomaly

F1’s salary 30000 → 40000.
F1 appears in as many rows as (student, course) pairs he teaches.
The UPDATE must touch **all** those rows. Miss one → two salaries for one human.

```sql
-- looks innocent, but it rewrites the same fact many times
UPDATE StudentCourseFaculty
SET Salary = 40000
WHERE FID = 'F1';
```

> **Exam-ready one-liner**
> An **anomaly** is a correctness problem that appears while inserting, deleting or updating, caused by mixing multiple real-world facts in one relation.

### 5. The instinctive fix (preview of later lectures)

Split by **subject**:

```text
Student  (SID, SName)              PK = SID
Course   (CID, CName)              PK = CID
Faculty  (FID, FName, Salary)      PK = FID
```

plus later the **relationship** tables that actually connect them (enrols, teaches).
Now:

- new course → insert into `Course` only
- delete a student → course/faculty survive
- change F1 salary → **one** row

This is the *idea*. The *discipline* that tells you **which** split is legal is **functional dependency + normal forms**.

### 6. Memory hook

**I-D-U**: Insert blocked, Delete over-kills, Update multi-writes.
Fat table = teen bimari. Normalization = ilaaj.

---

## Lec 25 · First Normal Form (1NF)

### 1. Intuition

A cell is a box. One box, one value.
“Sai registered in C **and** C++” written inside a single Course cell is a **list**, not a value.
Relational algebra does not know how to compare lists inside a cell.

### 2. Technical definition

A relation is in **First Normal Form** iff every attribute is **atomic** (indivisible) and there are **no repeating groups**.
Equivalently (Codd): the domains of all attributes are scalar; no attribute contains a set, list or relation.

> **Exam-ready definition**
> A relation is in 1NF if it contains only atomic values, i.e., no multivalued or composite attribute is stored in a single cell.

### 3. Counterexample (not in 1NF)

| Roll | Name | Course |
|---|---|---|
| 1 | Sai | {C, C++} |
| 2 | Harsh | {Java} |
| 3 | Omkar | {C, DBMS} |

Even **one** multivalued cell kills 1NF.

### 4. Three conversions the lecture gives

#### Method 1 — Flatten (repeat the owner columns)

| Roll | Name | Course |
|---|---|---|
| 1 | Sai | C |
| 1 | Sai | C++ |
| 2 | Harsh | Java |
| 3 | Omkar | C |
| 3 | Omkar | DBMS |

- Now atomic → **in 1NF**.
- `Roll` alone is no longer unique.
- PK = **(Roll, Course)** composite.

#### Method 2 — Fixed extra columns

| Roll | Name | Course1 | Course2 |
|---|---|---|---|
| 1 | Sai | C | C++ |
| 2 | Harsh | Java | NULL |
| 3 | Omkar | C | DBMS |

- PK can be `Roll` again.
- **NULL explosion** if one student takes 1 course and another takes 10.
- Schema must change if a student takes an 11th course.
- Legal 1NF, **bad design**.

#### Method 3 — Separate table (the good one)

```text
Student ( Roll, Name )                 PK = Roll

Takes   ( Roll, Course )               PK = (Roll, Course)
          FK Roll → Student.Roll
```

- Base table stays one-row-per-student.
- N courses ⇒ N rows in `Takes`, zero schema change.
- This is also how a **multivalued attribute** is mapped from ER.

> **Continuity**
> Method 3 is the same “+1 table for a multivalued attribute” rule used in ER-to-relational counting (Lec 22).

### 5. Traps

- “NULL is zero.” **No.** NULL = value does not exist.
- “If I make Course1, Course2 I am in 2NF.” You are only fighting 1NF, and poorly.
- Repeating `Name` in Method 1 is redundancy — 1NF **allows** it. Higher NFs will complain later.

### 6. Memory hook

**1NF = Atomic. One cell, one value.**

### 7. Quick check

Is a column `FullName = 'Ravi Kumar'` a 1NF violation?
**No** (unless the schema treats first/last as separate meaningful attributes you intend to query independently). 1NF forbids *multiple values of the same attribute*, not a string that a human can mentally split.

---

## Lec 27 · Functional Dependency (taught before Closure, used everywhere after)

*(Video number 27, but conceptually this is the tool. We place it before 2NF.)*

### 1. Intuition

`X → Y` means:
if I am confused about Y, I walk over to X, and **X settles the confusion**.

Two rows named Ranjit. Same person or two people?
Look at SID. Different SID → two people. Same SID → same person, data typed twice.

### 2. Technical definition

Let \(R\) be a relation, and \(X, Y \subseteq\) attributes of \(R\).

**\(X \rightarrow Y\)** (X functionally determines Y) iff
in every legal instance of \(R\),
whenever two tuples agree on \(X\), they also agree on \(Y\).

- \(X\) = **determinant**
- \(Y\) = **dependent**

Spoken: “X determines Y” / “Y is determined by X”.

### 3. Why the rule is true (the four cases)

Assume `SID → SName`.

| Case | SID | SName | Valid? | Why |
|---|---|---|---|---|
| 1 | 1, 1 | Ranjit, Ranjit | **Yes** | Same student written twice |
| 2 | 1, 2 | Ranjit, Ranjit | **Yes** | Two students, coincidentally same name |
| 3 | 1, 2 | Ranjit, Varun | **Yes** | Two different students |
| 4 | 1, 1 | Ranjit, Varun | **NO** | One SID cannot own two names |

![Figure B.2 Four FD cases](images/07_fd_four_cases.png)

**Figure B.2 — The only illegal pattern: same X, different Y.**

> **Galti se bhi mat bhoolna**
> Same Y, different X is **legal**.
> Names can collide. IDs cannot collide if ID → Name.

### 4. Trivial vs non-trivial — lecture vs standard

**Lecture said:**
- Trivial iff \(Y \subseteq X\) (also: \(X \cap Y \neq \emptyset\)).
- Non-trivial iff \(X \cap Y = \emptyset\).

**Standard terminology is finer. Do not mix them in a 2-mark definition.**

| Name | Condition | Example |
|---|---|---|
| **Trivial** FD | \(Y \subseteq X\) | `SID → SID`, `{SID, Name} → SID` |
| **Non-trivial** FD | \(Y \not\subseteq X\) (something on RHS is new) | `{SID, Name} → {SID, City}` |
| **Completely non-trivial** FD | \(X \cap Y = \emptyset\) | `SID → Name` |

Trivial FDs are **always** true (reflexivity). Never test them with the 4 cases.
The lecture’s “non-trivial = intersection empty” is actually **completely non-trivial**.
In 3NF/BCNF statements, textbooks say **non-trivial** (not completely non-trivial).

> **Source fidelity flag**
> Use the **standard** three-way split in exams unless the paper itself uses the lecture’s binary split.

### 5. Armstrong’s axioms and useful derived rules

Armstrong’s **sound and complete** trio:

1. **Reflexivity.** If \(Y \subseteq X\) then \(X \rightarrow Y\).
2. **Augmentation.** If \(X \rightarrow Y\) then \(XZ \rightarrow YZ\).
3. **Transitivity.** If \(X \rightarrow Y\) and \(Y \rightarrow Z\) then \(X \rightarrow Z\).

Derived (also always used):

4. **Union.** \(X \rightarrow Y\) and \(X \rightarrow Z\) ⇒ \(X \rightarrow YZ\).
5. **Decomposition (projection).** \(X \rightarrow YZ\) ⇒ \(X \rightarrow Y\) and \(X \rightarrow Z\).
6. **Pseudo-transitivity.** \(X \rightarrow Y\) and \(WY \rightarrow Z\) ⇒ \(WX \rightarrow Z\).
7. **Composition.** \(X \rightarrow Y\) and \(Z \rightarrow W\) ⇒ \(XZ \rightarrow YW\).

![Figure B.3 Armstrong properties](images/08_armstrong_axioms.png)

**Figure B.3 — FD properties.** Transitivity feeds 3NF. Decomposition is legal **only on the RHS**.

> **THE landmine (5-mark favourite)**
> \(XY \rightarrow Z\) does **NOT** give \(X \rightarrow Z\) or \(Y \rightarrow Z\).
> You may split the **right** side. You may **never** split the **left** side.
>
> Intuition: `{Roll, Exam}` together determine `Marks`. Roll alone does not.

### 6. Exam-ready definition

> Functional dependency \(X \rightarrow Y\) holds on \(R\) if for any two tuples \(t_1, t_2\) of any legal instance of \(R\), \(t_1[X] = t_2[X]\) implies \(t_1[Y] = t_2[Y]\).

### 7. Memory hook

**Same X ⇒ same Y. Always.**
**Split right, never left.**

### 8. Quick check

Given `AB → C`. Does `A → C` hold?
**Not from this FD.** Need more information.

---

## Lec 26 · Attribute Closure & Candidate Keys

### 1. Intuition

Closure \(X^+\) = “starting from X, using the given FDs as roads, which attributes can I **reach**?”

If I can reach **every** column, X can identify the whole row → X is a **superkey**.
If I can also throw nothing away, X is a **candidate key**.

### 2. Technical definition

The **attribute closure** of \(X\) w.r.t. a set of FDs \(F\), written \(X^+\), is the set of all attributes \(A\) such that \(F \models X \rightarrow A\).

- If \(X^+ =\) all attributes of \(R\), then \(X\) is a **superkey**.
- A **candidate key** is a **minimal** superkey (no proper subset is a superkey).
- **Prime attribute** = attribute that appears in **at least one** candidate key.
- **Non-prime attribute** = attribute that appears in **no** candidate key.

![Figure B.4 Closure method](images/09_closure_method.png)

**Figure B.4 — Closure algorithm and the superkey vs candidate-key distinction.**

### 3. Algorithm (write this in numerical answers)

```
X⁺ ← X                              // reflexivity
repeat
    for each FD  Y → Z  in F:
        if Y ⊆ X⁺:  X⁺ ← X⁺ ∪ Z    // transitivity / union
until X⁺ stops growing
```

### 4. Fast candidate-key heuristic (saves GATE time)

Look at **all RHS attributes**.
Any attribute that **never appears on any RHS** cannot be determined by others, so it **must sit in every candidate key**.
Start closures from those forced attributes.

Then the replacement trick:
if you already have a CK, and some attribute \(A\) of that CK appears on the RHS of \(W \rightarrow A\), try replacing \(A\) by \(W\) and test the new set’s closure.

> **Galti se bhi mat bhoolna**
> Finding **one** candidate key is not enough for 2NF / 3NF / BCNF.
> Missing a CK changes the prime-attribute set, and the whole answer flips.

### 5. Worked example 1 — unique CK

\(R(A,B,C,D)\)
\(F = \{ A \rightarrow B,\; B \rightarrow C,\; C \rightarrow D \}\)

| Set | Closure | Verdict |
|---|---|---|
| \(A^+\) | \(A,B,C,D\) | **candidate key** |
| \(B^+\) | \(B,C,D\) | not a key |
| \(C^+\) | \(C,D\) | not a key |
| \(D^+\) | \(D\) | not a key |
| \(AB^+\) | \(A,B,C,D\) | **superkey**, not candidate (`A` already works) |

- Candidate keys = \(\{A\}\)
- Prime = \(\{A\}\)
- Non-prime = \(\{B,C,D\}\)

### 6. Worked example 2 — cycle, everyone is a key

\(R(A,B,C,D)\)
\(F = \{ A \rightarrow B,\; B \rightarrow C,\; C \rightarrow D,\; D \rightarrow A \}\)

Each singleton closes to `ABCD`.
Candidate keys = \(\{A\},\{B\},\{C\},\{D\}\).
Prime = \(\{A,B,C,D\}\).
Non-prime = \(\emptyset\).

### 7. Worked example 3 — the replacement method

\(R(A,B,C,D,E)\)
The lecture’s FDs, reconstructed so that every closure the teacher computed is correct:

\[
F = \{ A \rightarrow B,\;\; BC \rightarrow D,\;\; D \rightarrow A,\;\; E \rightarrow C \}
\]

RHS attributes = \(\{A,B,C,D\}\). **E never appears on an RHS ⇒ E is in every CK.**

\(E^+ = \{E,C\}\) — not a key, but E is a **must-include**.

\(AE^+ = \{A,E,B,C,D\} = R\) → **AE is a CK.**

Replacement:
- `A` appears on RHS of `D → A` → try **DE**.
  \(DE^+ = \{D,E,A,B,C\} = R\) → **DE is a CK.**
- `D` appears on RHS of `BC → D`. Replacing D by B (E stays): **BE**.
  \(BE^+ = \{B,E,C,D,A\} = R\) → **BE is a CK.**
- Replacing D by C: **CE**.
  \(CE^+ = \{C,E\}\) → **not** a CK.

Candidate keys = **AE, BE, DE**.
Prime = \(\{A,B,D,E\}\).
Non-prime = \(\{C\}\).

### 8. Exam-ready statements

> \(X^+\) is the set of attributes functionally determined by \(X\). \(X\) is a candidate key iff \(X^+ = R\) and no proper subset of \(X\) has this property.
>
> Prime attributes are those that belong to some candidate key.

### 9. Memory hook

**Closure = reachability. Full reach + minimal = candidate key.**
**Never-on-RHS = invited to every key party.**

### 10. Quick check

If \(A\) is a candidate key, is \(AB\) a candidate key?
**No.** It is a **superkey**. Extra attribute destroys minimality.

---

# PART C — THE NORMAL FORMS
## Lec 28 · Second Normal Form (2NF)

### 1. Intuition

Composite key `{CustomerID, StoreID}` identifies a visit.
But `Location` is a fact about the **store**, not about the visit.
You are hanging a store-fact on **half** a visit-key.
That half-hanging is **partial dependency**.

Simple bhasha: *poori chaabi ke ek tukde se non-key column nikal aaye to 2NF toot gaya.*

### 2. Technical definition

A relation is in **2NF** iff

1. it is in **1NF**, and
2. every **non-prime** attribute is **fully functionally dependent** on **every candidate key**.

Equivalently: it contains **no partial dependency**.

### 3. What is a partial dependency?

FD \(X \rightarrow A\) is a **partial dependency** when **both** hold (**AND**):

1. \(X\) is a **proper subset** of **some** candidate key, and
2. \(A\) is **non-prime**.

```
PD  ⇔  (LHS proper⊂ some CK)   AND   (RHS non-prime)
```

- Proper subset of `{A,B}` is `{A}` or `{B}`, **not** `{A,B}`.
- `{A,B}` is a subset, but **not** a proper subset. `AB → C` is **full** dependence, not partial.

![Figure C.1 Partial dependency](images/10_2nf_partial.png)

**Figure C.1 — Location depends on StoreID, which is only part of the composite key.**

### 4. Why?

If a non-prime depends on part of a key, that fact is repeated in every row that reuses that part.
That is exactly the column-level redundancy of Lec 24.

If **every** candidate key is a **single** attribute, no proper subset can determine a non-prime in a non-trivial way → **2NF is automatic**.

### 5. Lecture example — Customer / Store / Location

```text
CustomerStore ( CustomerID, StoreID, Location )
CK = {CustomerID, StoreID}
Prime = {CustomerID, StoreID}
Non-prime = {Location}
```

Observed FD: `StoreID → Location`.

- LHS `StoreID` is a proper subset of the CK. **True.**
- RHS `Location` is non-prime. **True.**
- **Partial dependency exists → not in 2NF.**

**Decompose:**

```text
CS ( CustomerID, StoreID )     CK = {CustomerID, StoreID}
SL ( StoreID, Location )       CK = StoreID
```

Now `Location` depends on a **full** candidate key. Both results are in 2NF.

> **Source fidelity flag (lecture slip)**
> Around 6:09 the teacher says CustomerID and StoreID “are non-prime”.
> That is a **slip**. They form the candidate key, so they are **prime**.
> Non-prime in that example is **only Location**.

### 6. GATE-style worked example (from the lecture)

\(R(A,B,C,D,E,F)\)
\(F = \{ C \rightarrow F,\; E \rightarrow A,\; EC \rightarrow D,\; A \rightarrow B \}\)

**Step 1 — all candidate keys.**
RHS = \(\{F,A,D,B\}\). Never-on-RHS = \(\{E,C\}\).
\(EC^+ = \{E,C,F,A,D,B\} = R\).
Neither E nor C appears on any RHS → **only CK is EC**.

**Step 2 — primes / non-primes.**
Prime = \(\{E,C\}\).
Non-prime = \(\{A,B,D,F\}\).

**Step 3 — test each given FD for PD.**

| FD | LHS proper ⊂ CK? | RHS non-prime? | PD? |
|---|---|---|---|
| \(C \rightarrow F\) | Yes (`C` ⊂ `EC`) | Yes | **YES** |
| \(E \rightarrow A\) | Yes | Yes | **YES** |
| \(EC \rightarrow D\) | **No** (`EC` is the CK, not a proper subset) | Yes | no (full) |
| \(A \rightarrow B\) | **No** (`A` is not ⊂ `EC`) | Yes | no *(not a 2NF-PD on a given FD)* |

Even one PD ⇒ **not in 2NF**.

(Strictly, \(F^+\) also contains \(E \rightarrow B\) by transitivity, which is another PD. You already have enough to stop.)

### 7. Traps

| Trap | Truth |
|---|---|
| 2NF uses OR like 3NF | **No.** PD test is **AND**. |
| `AB → C` is partial if CK is AB | **No.** That is full. |
| Prime determined by part of a key breaks 2NF | **No.** 2NF only protects **non-primes**. |
| One CK is enough | **No.** PD is w.r.t. **any** CK. |
| In 2NF ⇒ in 3NF | **No.** See the nesting diagram. |

### 8. Exam-ready answer

> A relation is in 2NF if it is in 1NF and every non-prime attribute is fully functionally dependent on every candidate key; equivalently, it has no partial dependency. A partial dependency is an FD whose left side is a proper subset of a candidate key and whose right side is a non-prime attribute.

### 9. Memory hook

**2NF = no half-key → non-prime.**
Test = **AND**. Proper-subset **and** non-prime.

### 10. Quick check

CK = `{A,B}`. FD `A → B`. Is this a 2NF violation?
**No.** RHS `B` is prime.

---

## Lec 29 · Third Normal Form (3NF)

### 1. Intuition

`Roll → State` is healthy (key determines a fact).
`State → City` is a second hop through a **non-key**.
Now `City` is really a fact about `State`, but you stored it in the student table.
Change “Punjab’s capital city spelling” and you touch every Punjabi student.
That hop is **transitive dependency**.

### 2. Technical definition (two equivalent views)

**Theory view (Codd, as the lecture starts):**
A relation is in **3NF** if it is in **2NF** and has **no transitive dependency** of a **non-prime** attribute on a candidate key.

The only forbidden story:

```
non-prime  →  non-prime
```

(when this is not already covered by a superkey on the left).

**Question-solving view (use this in GATE):**
For **every** non-trivial FD \(X \rightarrow A\):

```
X is a superkey     OR     A is a prime attribute
```

The connective is **OR**, not AND.
(If \(X\) is a candidate key it is automatically a superkey.)

> **Standard wording uses SUPERKEY, not “candidate key only”.**
> The lecture often says “candidate key or superkey”. Writing **superkey** is the accurate exam phrase.

### 3. Why?

3NF stops a non-key from being the official source of another non-key.
Keys may determine anything.
Primes are already “key material”, so `D → A` with `A` prime is tolerated (this leftover is exactly what BCNF will later forbid).

### 4. Example — not in 3NF

```text
Student ( Roll, State, City )
CK = {Roll}
Prime = {Roll}
Non-prime = {State, City}
FDs:  Roll → State ,  State → City
```

`State → City`:
- LHS is **not** a superkey.
- RHS `City` is **not** prime.
- Forbidden. Also `Roll → State → City` is the classic transitive chain.

### 5. Abstract twin

\(R(A,B,C,D)\), \(F = \{ AB \rightarrow C,\; C \rightarrow D \}\).

- \(AB^+ = ABCD\) → CK = `{AB}` (assuming nothing else).
- Prime = `{A,B}`. Non-prime = `{C,D}`.
- `AB → C` : LHS is a CK → OK.
- `C → D` : LHS not a superkey, `D` non-prime → **not 3NF**.

If `C` *were* prime, or `D` *were* prime, this FD would pass 3NF.

### 6. The important “still 3NF” example

\(R(A,B,C,D)\)
\(F = \{ AB \rightarrow CD,\; D \rightarrow A \}\)

**Find ALL candidate keys.**
RHS = `{A,C,D}`. **B never on RHS ⇒ B in every CK.**

- \(AB^+ = ABCD\) → **AB is a CK.**
- `A` is on RHS of `D → A` → replace A by D → **DB**.
  \(DB^+ = \{D,B,A,C\} = R\) → **DB is a CK.**

Candidate keys = **AB, DB**.
Prime = `{A,B,D}`.
Non-prime = `{C}`.

Now test FDs (assume already in 2NF as the lecture does; you should still glance):

| FD | Superkey on LHS? | RHS prime? | 3NF? |
|---|---|---|---|
| \(AB \rightarrow CD\) | Yes (AB is a CK) | C no, D yes (mixed) | **OK** because LHS is a superkey |
| \(D \rightarrow A\) | **No** | **Yes** (`A` is prime) | **OK** by the OR |

**In 3NF. Not yet BCNF** (next lecture).

> **Yaad rakhna**
> Missing the second CK `DB` would make you think `A` is non-prime, and you would wrongly declare “not 3NF”.

### 7. 2NF vs 3NF check — do not swap the connectives

| | 2NF (PD exists if…) | 3NF (FD is legal if…) |
|---|---|---|
| Connective | **AND** | **OR** |
| LHS | proper subset of a CK | superkey |
| RHS | non-prime | prime |

### 8. Traps

- Checking only the primary key, ignoring other candidate keys.
- Treating `X → prime` as a 3NF violation. It is **allowed**.
- “In 3NF ⇒ in BCNF.” **False.**
- Calling every 2-hop a crime. `Roll → City` via a **prime** middle is not the crime; **non-prime → non-prime** is.

### 9. Exam-ready answer

> A relation is in 3NF if it is in 2NF and no non-prime attribute is transitively dependent on a candidate key. Equivalently, for every non-trivial FD \(X \rightarrow A\), either \(X\) is a superkey or \(A\) is prime.

### 10. Memory hook

**3NF = superkey on the left, OR prime on the right.**
**Sirf ek gunah: non-prime → non-prime.**

### 11. Quick check

CK = `{AB, DB}`. Is `D → A` allowed in 3NF?
**Yes**, because `A` is prime. (It will fail BCNF.)

---

## Lec 30 · Boyce–Codd Normal Form (BCNF)

### 1. Intuition

3NF still pardons one situation:
a **non-superkey** is allowed to determine a **prime**.
That leftover redundancy is rare but real (the classic “one teacher teaches only one subject, subject is part of a key”).

BCNF is the **strict special case of 3NF**:
the pardon is cancelled. **Every** determinant must be a superkey.

### 2. Technical definition

A relation is in **BCNF** iff it is in 3NF and, more strongly:

> For every **non-trivial** FD \(X \rightarrow Y\), \(X\) is a **superkey**.

The 3NF “OR RHS is prime” clause is **deleted**.

> **Exam-ready definition**
> A relation \(R\) is in BCNF if for every non-trivial functional dependency \(X \rightarrow Y\) that holds on \(R\), \(X\) is a superkey of \(R\).

(The lecture says “candidate key or superkey”. Official word is **superkey**. A candidate key is a special superkey, so an LHS that is a CK is fine.)

### 3. Why?

If something determines anything (beyond itself) it is acting like a key.
If it is not a key, the same determined fact will be repeated, and 3NF will not always catch it when the determined attribute is prime.

Cost of the extra strictness (standard theory, not from the lecture — know this for 2-marks):

- BCNF decomposition is always **lossless**.
- It may **fail to preserve** all FDs.
- 3NF can always be achieved lossless **and** dependency-preserving.

### 4. Lecture example — already in BCNF

```text
Student ( Roll, Name, VoterID, Age )
CKs given:  {Roll}, {VoterID}
```

FDs:

```
Roll     → Name
Roll     → VoterID
VoterID  → Age
VoterID  → Roll
```

Every LHS is a candidate key → every LHS is a superkey → **in BCNF**
(and therefore also in 3NF, 2NF, 1NF).

### 5. The 3NF-but-not-BCNF specimen (same as Lec 29)

\(R(A,B,C,D),\quad F=\{AB \rightarrow CD,\; D \rightarrow A\}\)
CKs = `{AB, DB}`. Primes = `{A,B,D}`.

`D → A` : `A` is prime → **3NF yes**.
`D` is **not** a superkey (`D^+ = DA` ≠ `R`) → **BCNF no**.

This is the diagram you should be able to redraw in 20 seconds.

### 6. Nesting — the lecture’s most-asked T/F

![Figure C.2 Normal-form nesting](images/06_nf_nested_sets.png)

**Figure C.2 — Inclusion hierarchy.** Standing in 2NF does **not** put you inside 3NF. Standing in 3NF does **not** put you inside BCNF.

**Correct implications (one direction only):**

\[
\text{BCNF} \;\Rightarrow\; 3\text{NF} \;\Rightarrow\; 2\text{NF} \;\Rightarrow\; 1\text{NF}
\]

**False reverse implications:**

- In 2NF \(\not\Rightarrow\) in 3NF
- In 3NF \(\not\Rightarrow\) in BCNF
- In 1NF \(\not\Rightarrow\) anything higher

### 7. Side-by-side (must-revise table)

| | 1NF | 2NF | 3NF | BCNF |
|---|---|---|---|---|
| Prerequisite | — | 1NF | 2NF | 3NF (in practice) |
| Forbids | multi-valued cells | partial dep. (half CK → non-prime) | non-prime → non-prime / bad transitivity | **any** non-superkey determinant |
| Check per FD | atomicity | LHS proper⊂CK **AND** RHS non-prime ⇒ fail | LHS superkey **OR** RHS prime ⇒ pass | LHS **must** be superkey |
| Strength | weakest | | | strongest of these four |

### 8. Traps

- “Special case of 3NF” does **not** mean “same as 3NF”.
- Checking only the primary key’s FDs.
- Forgetting trivial FDs are exempt (`Y ⊆ X` need not have X as a superkey — they always hold).
- Assuming BCNF is always the design goal. Sometimes we **stop at 3NF** to keep an FD.

### 9. Memory hook

**3NF = superkey OR prime.**
**BCNF = superkey. Full stop.**

### 10. Quick check

A relation with **two attributes** is always in BCNF. Why?
The only possible non-trivial FD is one attribute → the other, which makes that attribute a candidate key, hence a superkey.

---

# PART D — PRACTICE COMPANION
Questions use **only** ideas already taught.  
“Previous-year” is used **only** for the two questions whose official papers we quoted. Everything else is **exam-style**.

---

## D1. MCQs

**Q1.** A weak entity is identified by
(A) its own primary key
(B) a foreign key alone
(C) owner primary key + partial key
(D) any superkey of the owner

**Q2.** Identifying relationship is drawn as
(A) single rectangle
(B) double rectangle
(C) single diamond
(D) double diamond

**Q3.** (GATE CSE 2005 Q.75) \(E_1, E_2\) simple-valued; \(R_1\) is 1:N; \(R_2\) is M:N; neither relationship has attributes. Minimum tables?
(A) 2 (B) 3 (C) 4 (D) 5

**Q4.** For an M:N relationship with no attributes, the relationship table’s primary key is
(A) PK of either entity
(B) PK of the many side
(C) composite of both entity PKs
(D) a newly generated surrogate only — composites are illegal

**Q5.** (GATE CSE 2018 Q.11) \(R\) is M:1 from \(E_1\) to \(E_2\); both participate totally; \(|E_1| > |E_2|\). Which is true?
(A) Every entity in \(E_1\) is associated with exactly one entity in \(E_2\)
(B) Some entity in \(E_1\) is associated with more than one entity in \(E_2\)
(C) Every entity in \(E_2\) is associated with exactly one entity in \(E_1\)
(D) Every entity in \(E_2\) is associated with at most one entity in \(E_1\)

**Q6.** Which operation can lose a still-true course fact just because the last enrolled student was deleted?
(A) insertion anomaly
(B) deletion anomaly
(C) updation anomaly
(D) selection anomaly

**Q7.** A cell stores `{C, C++}`. The relation is not in
(A) BCNF only
(B) 3NF only
(C) 1NF
(D) it is in 1NF; sets are atomic

**Q8.** `SID → SName` is violated by which pair of tuples?
(A) (1, Ranjit), (1, Ranjit)
(B) (1, Ranjit), (2, Ranjit)
(C) (1, Ranjit), (2, Varun)
(D) (1, Ranjit), (1, Varun)

**Q9.** From `XY → Z` we can legally infer
(A) `X → Z`
(B) `Y → Z`
(C) both (A) and (B)
(D) neither (A) nor (B)

**Q10.** \(R(A,B,C,D),\ F=\{A\rightarrow B, B\rightarrow C, C\rightarrow D\}\). Candidate key(s)?
(A) A only
(B) A and AB
(C) A, B, C, D
(D) AB only

**Q11.** An attribute that appears in at least one candidate key is
(A) super attribute
(B) prime attribute
(C) foreign attribute
(D) derived attribute

**Q12.** Partial dependency is
(A) proper subset of a CK → non-prime
(B) superkey → non-prime
(C) non-prime → prime
(D) CK → CK

**Q13.** The 3NF legality test uses
(A) AND
(B) OR
(C) XOR
(D) NAND

**Q14.** \(R(A,B,C,D),\ F=\{AB\rightarrow CD, D\rightarrow A\}\). The relation is
(A) in BCNF
(B) in 3NF but not BCNF
(C) in 2NF but not 3NF
(D) not in 2NF

**Q15.** If a table is in 2NF, it
(A) must be in 3NF
(B) must be in BCNF
(C) must be in 1NF
(D) cannot be in 1NF

**Q16.** BCNF drops which 3NF mercy?
(A) allowing partial dependency
(B) allowing a non-superkey to determine a prime
(C) allowing multivalued attributes
(D) allowing trivial FDs

**Q17.** Owner entity of a weak entity usually participates
(A) totally, always
(B) partially, typically
(C) never
(D) only in M:N

**Q18.** Attribute that never appears on any RHS of the given FDs
(A) cannot be prime
(B) must belong to every candidate key
(C) is always non-prime
(D) can be dropped from the relation

---

### D1 Answer key

| Q | Ans | Q | Ans |
|---|---|---|---|
| 1 | C | 10 | A |
| 2 | D | 11 | B |
| 3 | B | 12 | A |
| 4 | C | 13 | B |
| 5 | A | 14 | B |
| 6 | B | 15 | C |
| 7 | C | 16 | B |
| 8 | D | 17 | B |
| 9 | D | 18 | B |

**Only the traps, briefly**

- **Q3:** naive 4 is option (C). Merge only the 1:N.
- **Q5:** M:1 + total on \(E_1\) = *exactly one*. \(|E_1|>|E_2|\) kills (C) and (D).
- **Q9:** never split LHS.
- **Q10:** `AB` is a superkey, not a candidate key.
- **Q14:** `D → A` with `A` prime saves 3NF, fails BCNF. CKs are AB and DB; non-prime is only C; no PD.

---

## D2. Fill in the blanks

1. Partial key is shown with a __________ underline.
2. In 1:N mapping, the foreign key is placed on the __________ side.
3. Same determinant, different dependent ⇒ FD is __________.
4. \(X^+ = R\) and no proper subset has this property ⇒ \(X\) is a __________.
5. 2NF PD test connective is __________ ; 3NF legality connective is __________.
6. BCNF requires every __________ of a non-trivial FD to be a __________.
7. Row-level duplication is removed by a __________ ; column-level harmful duplication by __________.

**Answers:** 1. dotted/dashed  2. many (N)  3. invalid / violated  4. candidate key  5. AND ; OR  6. determinant (LHS) ; superkey  7. primary key ; normalization

---

## D3. True / False with justification

1. **T/F:** Every BCNF relation is in 3NF.
2. **T/F:** Every 3NF relation is in BCNF.
3. **T/F:** If every candidate key is a single attribute, the relation is in 2NF (given it is in 1NF).
4. **T/F:** A weak entity can be stored without any foreign key.
5. **T/F:** `AB → C` implies `A → C`.
6. **T/F:** Trivial FDs must be checked against sample tuples before accepting them.
7. **T/F:** For minimum tables, an M:N relationship can be merged into either entity.
8. **T/F:** Prime attribute = attribute of the *primary* key only.

**Answers**

1. **True.** BCNF ⇒ 3NF ⇒ 2NF ⇒ 1NF.
2. **False.** Counterexample: `AB → CD`, `D → A` on `ABCD`.
3. **True.** No proper subset of a singleton key can carry a non-trivial PD.
4. **False.** Identification uses owner PK as FK.
5. **False.** Cannot decompose LHS.
6. **False.** Trivial FDs are identically true by reflexivity.
7. **False.** M:N always needs its own table (or you break 1NF).
8. **False.** Prime = member of **any** candidate key, including alternate keys.

---

## D4. One-mark questions

1. Symbol for a weak entity set?
2. Who proposed 1NF / 2NF / 3NF? (lecture: E. F. Codd)
3. Write the 4th (illegal) FD case in one line.
4. Define prime attribute in one line.
5. State Armstrong’s three axioms by name.
6. What is existence dependency?
7. Give the BCNF condition in one line.

**Short answers**

1. Double rectangle.
2. E. F. Codd. (BCNF: Boyce and Codd, 1974.)
3. Two tuples with the same X and different Y.
4. An attribute that is part of some candidate key.
5. Reflexivity, augmentation, transitivity.
6. A weak entity cannot exist without its owner; it participates totally in the identifying relationship.
7. Every non-trivial FD has a superkey on the left.

---

## D5. Short answers (3–5 marks)

**S1.** Convert Employee–HAS–Dependent to tables. State PKs and FKs.

**S2.** Why is the minimum number of tables 3 in GATE 2005 Q.75? Write the three schemas.

**S3.** Distinguish insertion, deletion and updation anomalies with one university example each.

**S4.** Give three methods to achieve 1NF from a multivalued `Course` attribute. Which is preferred and why?

**S5.** Compute all candidate keys, primes and non-primes for
\(R(A,B,C,D,E),\ F=\{A\rightarrow B, BC\rightarrow D, D\rightarrow A, E\rightarrow C\}\).

**S6.** Check 2NF for
\(R(A,B,C,D,E,F),\ F=\{C\rightarrow F, E\rightarrow A, EC\rightarrow D, A\rightarrow B\}\).
Show the PD test table.

**S7.** Prove that \(R(A,B,C,D)\) with \(AB\rightarrow CD,\ D\rightarrow A\) is in 3NF but not in BCNF.

---

### Indicative answers for S1, S2, S5, S7

**S1.** See Part A §6. Two tables. `Employee(EID PK)`. `HasDependent(EID, Name, Age)` with PK `(EID, Name)`, FK `EID → Employee`.

**S2.** See Part A Lec 22. Schemas:
`E1(A)`, `E2(B, A)`, `R2(A,B)`.

**S5.** CKs = AE, BE, DE. Prime = A,B,D,E. Non-prime = C.
(Closures computed in Part B Lec 26.)

**S7.**
CKs: B is never on RHS. `AB⁺ = ABCD`. Replace A by D (because `D → A`) → `DB⁺ = DBAC = R`.
CKs = {AB, DB}. Prime = {A,B,D}. Non-prime = {C}.
`AB → CD`: LHS superkey → 3NF OK, BCNF OK.
`D → A`: A prime → 3NF OK. D not a superkey (`D⁺ = DA`) → BCNF FAIL.

---

## D6. Long answers (include a diagram)

**L1.** Draw the Chen diagram for Employee / Dependent. Mark every special symbol. Then write the relational mapping and a `CREATE TABLE` script. (8–10 marks)

**L2.** Explain the normal-form inclusion hierarchy with a nested-set diagram. Give one true and two false implication statements that examiners love. (6–8 marks)

**L3.** Starting from a mixed `Student-Course-Faculty` table, show one insertion, one deletion and one updation anomaly, then decompose and show why each anomaly disappears. (8 marks)

---

## D7. Applied / numerical

**N1.** \(R(A,B,C,D),\ F=\{A\rightarrow B, B\rightarrow C, C\rightarrow D\}\).
List \(A^+, B^+, C^+, D^+\). Identify keys, primes, non-primes.
Is the relation in 2NF? 3NF? BCNF?

**Solution.**
\(A^+=ABCD,\ B^+=BCD,\ C^+=CD,\ D^+=D\).
CK = {A}. Prime = {A}. Non-prime = {B,C,D}.
Single-attribute CK ⇒ **2NF** (no proper subset to cause PD).
`B → C`: B not superkey, C not prime ⇒ **not 3NF**, hence **not BCNF**.
(Also `A → B → C` is a transitive chain through a non-prime.)

**N2.** How many superkeys does a relation with *n* attributes have if it has **one** candidate key of *k* attributes?

**Derivation.**
The *k* attributes of that CK **must** be included.
Each of the remaining \(n-k\) attributes may be in or out: \(2^{n-k}\) possibilities.
So number of superkeys that **contain this CK** is \(2^{n-k}\).
If this is the **only** CK, that is the number of superkeys of \(R\).
If there are several CKs, take the union (avoid double-counting supersets that contain two CKs).

**N3.** \(R(A,B,C),\ F=\{A\rightarrow B, B\rightarrow A\}\).
CKs? Highest normal form?

**Solution.**
\(A^+=AB\) (not C). \(B^+=BA\) (not C).
Never-on-RHS = {C} ⇒ C in every CK.
`AC⁺ = ACB = R`, `BC⁺ = BCR = R`. CKs = {AC, BC}.
Prime = {A,B,C}. Non-prime = ∅.
No non-prime ⇒ no PD, no non-prime transitivity ⇒ **3NF**.
FDs `A → B` and `B → A`: LHS is not a superkey (missing C) ⇒ **not BCNF**.
Highest NF = **3NF**.

---

## D8. Match the following

| X | Y |
|---|---|
| 1. Double rectangle | a. Determinant must be superkey |
| 2. Dotted underline | b. Weak entity |
| 3. Proper ⊂ CK → non-prime | c. Partial key |
| 4. Superkey OR prime | d. Partial dependency / 2NF test |
| 5. BCNF | e. 3NF test |

**Answer:** 1-b, 2-c, 3-d, 4-e, 5-a.

---

## D9. Exam-style / HOTS

**H1.** (exam-style, not claimed as PYQ)
Two strong entities M, N; relationships \(R_1\) (1:1, both partial) and \(R_2\) (M:N). No relationship attributes, no multivalued attributes. Minimum tables?

**Reasoning.** 1:1 both partial → 2 tables (FK on one side). M:N adds a third. **Answer: 3.**

**H2.** In the weak-entity mapping, why is `ON DELETE CASCADE` from owner to weak table semantically right?

**Reasoning.** Existence dependency: if the owner disappears, the weak entity has no identity in this mini-world. Cascade implements that rule. (Restrict would block deleting an employee who still has dependents — also used in some businesses. Cascade matches the *model* the lecture taught.)

**H3.** A student argues: “`D → A` with A prime is a partial dependency, so the Lec-29 example is not even in 2NF.” Destroy the argument.

**Reasoning.** PD requires RHS **non-prime**. `A` is prime. 2NF does not police prime-to-prime FDs. That FD is a **BCNF** (not 2NF) issue.

**H4.** Why can Method-2 of 1NF (Course1, Course2, …) create an updation/insertion headache later?

**Reasoning.** The maximum number of courses becomes a **schema constant**. A new extra course needs `ALTER TABLE`. Sparse NULLs waste space and confuse uniqueness. You have turned a *value-count* problem into a *column-count* problem.

---

# PART E — QUICK REVISION & EXAM RADAR

## One-liners that fetch marks

| Concept | Exam-ready one-liner |
|---|---|
| Weak entity | No PK of its own; identified by owner PK + partial key; double rectangle. |
| Identifying relationship | Double diamond; weak side total. |
| Partial key | Discriminator; dotted underline. |
| Weak mapping | Merge weak + identifying rel; PK = (owner PK, partial key). |
| 1:N mapping | FK of one-side PK sits on the **many** side; R table droppable. |
| M:N mapping | Own table; composite PK of both entity PKs. |
| GATE 2005 min tables | 1:N merges, M:N does not → **3**. |
| Total + M:1 from E1 to E2 | Every E1 related to **exactly one** E2. |
| Normalization | Reduce redundancy / anomalies via FD-based decomposition. |
| Insertion anomaly | Cannot insert a fact because some other fact’s key is missing. |
| Deletion anomaly | Deleting one fact accidentally deletes another still-true fact. |
| Updation anomaly | One real-world change must be written in many rows. |
| 1NF | Atomic values only. |
| FD \(X\rightarrow Y\) | Same X ⇒ same Y, in every legal instance. |
| Illegal FD pattern | Same X, different Y. |
| Trivial FD | \(Y \subseteq X\); always true. |
| Do not split | Left-hand side of an FD. |
| Closure \(X^+\) | All attributes determined by X. |
| Superkey | \(X^+ = R\). |
| Candidate key | Minimal superkey. |
| Prime | Member of some candidate key. |
| Never-on-RHS | Belongs to **every** CK. |
| 2NF | 1NF + no partial dependency. |
| Partial dependency | Proper ⊂ CK **AND** RHS non-prime. |
| 3NF | For every non-trivial FD: LHS superkey **OR** RHS prime. |
| Forbidden 3NF story | non-prime → non-prime. |
| BCNF | Every non-trivial FD has superkey on LHS. |
| Nesting | BCNF ⇒ 3NF ⇒ 2NF ⇒ 1NF; reverses are false. |

## Most likely exam questions from *this* lecture block

1. Draw / convert a weak entity (symbols + 2 tables + composite PK).
2. Minimum tables for mixed 1:N and M:N (GATE 2005 clone).
3. M:1 + total participation true/false options (GATE 2018 clone).
4. Define the three anomalies with one example each.
5. Four cases of FD validity.
6. “Can we write `X → Z` from `XY → Z`?” 
7. Compute all candidate keys by closure + replacement.
8. Given FDs, classify 2NF / 3NF / BCNF with a check table.
9. T/F: in 2NF ⇒ in 3NF.
10. Exhibit a relation in 3NF but not BCNF.

## Memory traps (last look)

- Double rectangle ≠ double diamond. Entity vs relationship.
- Solid underline ≠ dotted underline.
- Minimum tables ≠ “one table per box in the ER diagram”.
- |E1| (set size) ≠ 1:N (relationship ratio).
- Superkey ⊃ candidate key ⊃ primary key. Do not swap.
- 2NF = **AND**. 3NF = **OR**. BCNF = **no OR**.
- Find **all** candidate keys before calling anything prime.
- Lecture slip: CustomerID/StoreID are **prime**, not non-prime.
- Lecture slip: “non-trivial = empty intersection” is **completely** non-trivial.
- Prefer **superkey** in 3NF/BCNF definitions.

## Final booster — recall without looking

```
Weak = double rectangle + double diamond + dotted key + total + composite PK

1:N  → FK on N          M:N → extra table
GATE 2005 → 3 tables     GATE 2018 → A (exactly one)

I-D-U anomalies          1NF = atomic

X → Y : same X ⇒ same Y
Split RHS, never LHS
X⁺ full & minimal = CK
Never-on-RHS ∈ every CK
Prime = in some CK

2NF: ¬ (proper⊂CK  AND  non-prime)
3NF: superkey  OR  prime
BCNF: superkey.

BCNF ⇒ 3NF ⇒ 2NF ⇒ 1NF
3NF example that fails BCNF: AB→CD , D→A
```

---

*End of notebook · Lec 21–30 · Verify every numerical by recomputing closures before you walk into the hall.*
