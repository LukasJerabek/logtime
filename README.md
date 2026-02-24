# 🕒 logtime
This is minimalistic time-tracking tool based on the presumption, that the simplest way to track time is by writing down the timestamp, when switching context.

Calculates statistics from timestamps and optionally sends them to Redmine api.

---

## How It Works

1. You prepare your daily file to track timestamps, where DAYOFWEEK is any of MO,TU,WE,TH,FR,SA,SU.
`root_folder/YYYY/MM/YYYY-MM-DD {DAYOFWEEK}.md`

2. After that you can start filling in the timestamps with optional task id and optional description.
Like this:
```
08:00 12345 Same description will be tracked together in statistics, and reported together in redmine.
08:30 12345 differing description will be tracked separately in statistics, also reported to redmine separately.
09:00 12345 Same description will be tracked together in statistics, and reported together in redmine.
09:10 45678
10:00 This will appear as work activity in statistics, but without task id can't be reported to redmine api.
10:10 organization
10:20 # lunch, hashtag marks nonworking activity
10:30 45678
11:00 # end, this was a short day
```
Records with only task id still work, but redmine report won't have any text.

4. Don't forget to check out your logtime/config.py. There you need to set your root_folder path of the daily failes. Also its possible to adjust defaults, that serves as a dictionary of texts, that you want to exchange for task id, so that you won't have to remember it.

5. After you run logtime it will:
   * Read timestamps and descriptions
   * Compute deltas between entries
   * Group by task and description
   * Produce a summary in your log file
   * Optionally send rounded hours to Redmine

6. Daily file will be extended with statistics
```
Summary:
40 = 0h 40m ~ 0.75h: 12345 same description will be tracked together in statistics, and reported together in redmine statistics
30 = 0h 30m ~ 0.5h: 12345 differing description will be tracked separately in statistics, also reported to redmine statistics separately.
80 = 1h 20m ~ 1.25h: 45678
10 = 0h 10m ~ 0.25h: This will appear as work activity in statistics, but without task id can't be reported to redmine api.
10 = 0h 10m ~ 0.25h: 77549 organization  # notice this has been updated with task id from defaults in logtime/config.py
10 = 0h 10m ~ 0.25h: # lunch, hashtag marks nonworking activity

total: 3h 0m (180)
total work: 2h 50m (170)
total work rounded hours: 3.0
total free:  0h 10m (10)
saldo: -5h 0m (-300)
working too little
already parsed
```

7. Finally you will be prompted with
`Send on api? (y/n):`
For redmine report to work, you also need to set environment variables REDMINE_API_KEY and REDMINE_URL first.

---

## How to run

- Clone this repo anywhere you want
`git clone https://github.com/LukasJerabek/logtime.git`
- Enter repo
`cd logtime`
- Read through the above "How It Works" section and do the necessary preparation.
- After preparation run logtime preferably with uv:
`uv run logtime --days-back <number>`
--days-back parameter lets you compute files older than today.

It is recommended to create some alias to run logtime for example in you .bashrc/.zshrc/...:
```
logtime() {
  pushd <where you cloned there repo>/logtime/ || return
  uv run logtime --days-back "$@"
  popd
}
```
After that you can just call `logtime <number>` from anywhere.

---

## Contributing

Contribution is welcome, however please keep the tool simple.

---

## License

This project is licensed under **MIT**.

---
