/**
 * Steezy Studio feedback: a web address that adds a row to the feedback sheet.
 *
 * Set up once (Stefan):
 *   1. Open the feedback Google Sheet, then Extensions > Apps Script.
 *   2. Paste this whole file over the default code. Save.
 *   3. Deploy > New deployment > type "Web app". Execute as: Me. Who has access: Anyone.
 *   4. Copy the web app URL (ends in /exec) and give it to Claude, who puts it in
 *      studio/feedback_config.py.
 *
 * The first row of the sheet should read:
 *   time | id | status | tool | version | os | note | log
 * Testers only ever add rows through this address. Status starts as "new"; Claude and
 * Stefan change it to "done" (or write a reply in a note) when handled.
 */
var TOKEN = "steezy-feedback-v1";      // must match studio/feedback_config.py (filters bots, not a secret)
var DAILY_CAP = 200;                   // rows per day in total, whoever sends them
var MAX_NOTE = 2000;
var MAX_LOG = 6000;

function plain(v, max) {
  // Stored as plain text: a leading = + - @ would otherwise run as a formula in Sheets.
  var s = String(v == null ? "" : v).slice(0, max);
  return /^[=+\-@]/.test(s) ? "'" + s : s;
}

function reply(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

function doPost(e) {
  var lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    var d = JSON.parse((e.postData && e.postData.contents) || "{}");
    if (d.token !== TOKEN || d.website) return reply({ok: false});
    var note = plain(d.note, MAX_NOTE);
    if (!note.trim()) return reply({ok: false});

    var props = PropertiesService.getScriptProperties();
    var today = Utilities.formatDate(new Date(), "UTC", "yyyy-MM-dd");
    var count = props.getProperty("day") === today ? Number(props.getProperty("count") || 0) : 0;
    if (count >= DAILY_CAP) return reply({ok: false, full: true});
    props.setProperties({day: today, count: String(count + 1)});

    SpreadsheetApp.getActiveSpreadsheet().getSheets()[0].appendRow([
      new Date(), plain(d.id, 40), "new", plain(d.tool, 40), plain(d.version, 20), plain(d.os, 60),
      note, plain(d.log, MAX_LOG)
    ]);
    return reply({ok: true});
  } catch (err) {
    return reply({ok: false});
  } finally {
    lock.releaseLock();
  }
}

function doGet() { return reply({ok: true, what: "Steezy Studio feedback"}); }
