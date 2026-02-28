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

## Notes
- The API key is required because the endpoint is public.
- If you change the deployment, update the URL in web/config.js.
- For daily prioritization, export the Results sheet as CSV and pass that URL to
  scripts/build_today.py.
- The Apps Script URL can return CSV directly after adding the doGet handler
  above (use the same /exec URL, optionally with ?format=csv).
