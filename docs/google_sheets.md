# Google Sheets results logging

This app can send quiz results to a Google Sheet via Apps Script.

## 1) Create the Sheet
1. Create a new Google Sheet named "Turkish Quiz Results".
2. Add a sheet named "Users" with two columns:
  - user_name
  - API_key
3. Result sheets will be created automatically as "Results_<user_name>" with
  these columns:
  - timestamp
  - word_id
  - mode
  - correct

## 2) Create the Apps Script
1. In the Sheet, go to Extensions -> Apps Script.
2. Replace the default script with:

```
var USERS_SHEET = "Users";

function getUserNameByApiKey(apiKey) {
  if (!apiKey) return "";
  var sheet = SpreadsheetApp.getActive().getSheetByName(USERS_SHEET);
  if (!sheet) return "";

  var values = sheet.getDataRange().getValues();
  if (!values || values.length < 2) return "";

  var header = values[0].map(function (cell) {
    return String(cell || "").trim();
  });
  var nameIndex = header.indexOf("user_name");
  var keyIndex = header.indexOf("API_key");
  if (nameIndex === -1 || keyIndex === -1) return "";

  for (var i = 1; i < values.length; i++) {
    var row = values[i];
    var rowKey = String(row[keyIndex] || "").trim();
    if (rowKey && rowKey === apiKey) {
      return String(row[nameIndex] || "").trim();
    }
  }

  return "";
}

function sanitizeSheetName(name) {
  var safe = String(name || "").trim();
  if (!safe) return "";
  safe = safe.replace(/[\[\]\\/?*]/g, "_").replace(/\s+/g, "_");
  return safe.substring(0, 80);
}

function getOrCreateResultsSheet(userName) {
  var safeName = sanitizeSheetName(userName);
  if (!safeName) return null;
  var sheetName = "Results_" + safeName;
  var sheet = SpreadsheetApp.getActive().getSheetByName(sheetName);
  if (!sheet) {
    sheet = SpreadsheetApp.getActive().insertSheet(sheetName);
    sheet.appendRow(["timestamp", "word_id", "mode", "correct"]);
  }
  return sheet;
}

function doPost(e) {
  var data = e.parameter || {};
  var apiKey = String(data.api_key || "").trim();
  var userName = getUserNameByApiKey(apiKey);
  if (!userName) {
    return ContentService.createTextOutput("Unauthorized");
  }

  var sheet = getOrCreateResultsSheet(userName);
  if (!sheet) {
    return ContentService.createTextOutput("Unauthorized");
  }

  sheet.appendRow([
    data.timestamp || "",
    data.word_id || "",
    data.mode || "",
    String(data.correct === "true")
  ]);

  return ContentService.createTextOutput("OK");
}

function doGet(e) {
  var data = e && e.parameter ? e.parameter : {};
  var apiKey = String(data.api_key || "").trim();
  var userName = getUserNameByApiKey(apiKey);
  if (!userName) {
    return ContentService.createTextOutput("Unauthorized");
  }

  if (String(data.action || "").trim().toLowerCase() === "whoami") {
    return ContentService.createTextOutput(userName);
  }

  var sheet = getOrCreateResultsSheet(userName);
  if (!sheet) {
    return ContentService.createTextOutput("timestamp,word_id,mode,correct");
  }

  var values = sheet.getDataRange().getValues();
  var rows = values.map(function (row) {
    return row.map(function (cell) {
      var value = "";
      if (cell === true) {
        value = "true";
      } else if (cell === false) {
        value = "false";
      } else if (cell !== null && cell !== undefined) {
        value = String(cell);
      }

      if (value.indexOf(",") >= 0 || value.indexOf("\"") >= 0) {
        value = '"' + value.replace(/"/g, '""') + '"';
      }
      return value;
    }).join(",");
  }).join("\n");

  return ContentService.createTextOutput(rows).setMimeType(
    ContentService.MimeType.CSV
  );
}
```

## 3) Deploy as a Web App
1. Click Deploy -> New deployment.
2. Select "Web app".
3. Execute as: "Me".
4. Who has access: "Anyone".
5. Click Deploy and copy the web app URL.
6. If you already deployed once, create a new deployment after changing the script.

## 4) Configure the web app
1. Open web/config.js.
2. Set resultsEndpoint to the web app URL.
3. Set resultsEnabled to true.
4. Commit and push.

## Finding duplicate rows in the sheet

A retried POST whose response was lost appends the same row twice (identical
timestamp, word_id, mode, correct). Scoring ignores them — `event_stream()` in
`build_today.py` and `eventStream()` in `web/today_scoring.js` drop exact
repeats — so pruning is hygiene, not a correctness fix.
`python3 scripts/stats_analysis.py` prints them explicitly.

To find them in the sheet, put these on a **separate sheet** (say `Dupes`), not
on the results sheet itself: the app appends to the results sheet constantly, and
a heavy formula there would be recalculated on every write. Replace `Results_ME`
with your own `Results_<user_name>` tab.

**Two gotchas before pasting anything:**
- A formula must be on **one line** — a quoted string cannot span lines, or Sheets
  reports a parse error (*kaavan jäsennysvirhe*).
- In a **Finnish/European locale the argument separator is `;`, not `,`**. Both
  variants are given below. (Inside a `QUERY` string the commas stay commas —
  that is query syntax, not affected by locale.)

**Simplest check — list every row whose timestamp appears more than once.**
Duplicates carry an identical millisecond timestamp, and two real answers never
do, so one column is enough (and it is far lighter than matching all four).
Put the **row number** in one cell and the data next to it, using the same
condition so the two line up (avoids array literals, whose column separator is
`\` in a Finnish locale):

```
A2:  =FILTER(ROW(Results_ME!A2:A); COUNTIF(Results_ME!A:A; Results_ME!A2:A) > 1)
B2:  =FILTER(Results_ME!A2:D;      COUNTIF(Results_ME!A:A; Results_ME!A2:A) > 1)
```

Comma-locale equivalent: replace each `;` with `,`.

To list **only the redundant copies** (skipping the first occurrence of each) —
i.e. exactly the rows to delete:

```
=FILTER(ROW(Results_ME!A2:A); (Results_ME!A2:A<>"") * (MATCH(Results_ME!A2:A; Results_ME!A2:A; 0) <> ROW(Results_ME!A2:A)-1))
```

`python3 scripts/stats_analysis.py` prints the same row numbers, plus a
ready-made bottom-up delete list.

**How many extra rows are there:**

```
=COUNTA(Results_ME!A2:A) - COUNTA(UNIQUE(Results_ME!A2:A))
=COUNTA(Results_ME!A2:A) - COUNTA(UNIQUE(Results_ME!A2:A))                 (same in both)
```

**Duplicated events with their copy count** (one line; note `;` for fi locale):

```
=QUERY(Results_ME!A2:D, "select Col1, Col2, Col3, Col4, count(Col1) where Col1 is not null group by Col1, Col2, Col3, Col4 having count(Col1) > 1 label count(Col1) 'copies'", 0)
=QUERY(Results_ME!A2:D; "select Col1, Col2, Col3, Col4, count(Col1) where Col1 is not null group by Col1, Col2, Col3, Col4 having count(Col1) > 1 label count(Col1) 'copies'"; 0)
```

## Actually removing the duplicates

**A formula cannot delete rows.** Sheets formulas are pure: they produce a value
in the cell that holds them and cannot modify the results sheet. So "show and
remove in one formula" is not possible. Three ways to do the removal:

**1. Built-in cleanup (easiest, in place, no script).**
Select the data range on the results sheet, then
*Data → Data cleanup → Remove duplicates*, with all four columns ticked and
"Data has header row" checked. It keeps the first occurrence of each identical
row and deletes the rest — exactly the intended pruning. Do it while the app is
not syncing, since it rewrites the sheet.

**2. Delete the listed rows by hand.** Use the row numbers from the formula above
or from `stats_analysis.py`, and delete **bottom-up** so earlier row numbers stay
valid. Fine when there are only a handful.

**3. Formula-produced clean copy.** On another tab:

```
=UNIQUE(Results_ME!A1:D)
```

then copy that range and *Paste special → Values only* over the results sheet.
This rewrites the whole sheet, so prefer option 1 unless you want to inspect the
cleaned data first.

(A menu-driven Apps Script macro could do it in one click, but that means
touching the script project, which is deliberately being avoided for now.)

## Notes
- The API key is required because the endpoint is public.
- If you change the deployment, update the URL in web/config.js.
- The web client now keeps a local retry queue for result submissions in
  localStorage. If a POST fails temporarily, the result stays queued and is
  retried later instead of being silently dropped.
- Because retries reuse the original client timestamp, a failed response can
  occasionally produce a duplicate row with the same timestamp, word_id, mode,
  and correct value. Those can be cleaned up manually in the sheet if needed.
- For daily prioritization, export the Results sheet as CSV and pass that URL to
  scripts/build_today.py.
- The Apps Script URL can return CSV directly after adding the doGet handler
  above (use the same /exec URL, optionally with ?format=csv).
