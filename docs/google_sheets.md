# Google Sheets results logging

This app can send quiz results to a Google Sheet via Apps Script.

## 1) Create the Sheet
1. Create a new Google Sheet named "Turkish Quiz Results".
2. Add a header row with these columns:
   - timestamp
   - word_id
   - mode
   - correct

## 2) Create the Apps Script
1. In the Sheet, go to Extensions -> Apps Script.
2. Replace the default script with:

```
function doPost(e) {
  var sheet = SpreadsheetApp.getActive().getSheetByName("Results");
  if (!sheet) {
    sheet = SpreadsheetApp.getActive().insertSheet("Results");
    sheet.appendRow(["timestamp", "word_id", "mode", "correct"]);
  }

  var data = {};
  try {
    data = JSON.parse(e.postData.contents);
  } catch (err) {
    return ContentService.createTextOutput("Invalid JSON");
  }

  sheet.appendRow([
    data.timestamp || "",
    data.word_id || "",
    data.mode || "",
    String(Boolean(data.correct))
  ]);

  return ContentService.createTextOutput("OK");
}
```

## 3) Deploy as a Web App
1. Click Deploy -> New deployment.
2. Select "Web app".
3. Execute as: "Me".
4. Who has access: "Only myself".
5. Click Deploy and copy the web app URL.

## 4) Configure the web app
1. Open web/config.js.
2. Set resultsEndpoint to the web app URL.
3. Set resultsEnabled to true.
4. Commit and push.

## Notes
- You must be signed into the same Google account on your phone.
- If you change the deployment, update the URL in web/config.js.
