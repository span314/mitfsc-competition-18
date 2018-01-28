#!/usr/bin/python
from csv import DictReader
from collections import defaultdict

# save spreadsheet to csv
# read entries into dictionary of event to list of entries
event_entries = defaultdict(list)
with open("entries.csv", "r") as file_in:
    reader = DictReader(file_in)
    for entry in reader:
        event = entry["Event"].title().strip()
        if entry["Gender"] == "Male".title().strip():
            if "Short" in event:
                event = event.replace("Short Program", "Mens Short Program")
            elif "Freeskate" in event:
                event = event.replace("Freeskate", "Mens Freeskate")
            elif "Championship" in event:
                event = event.replace("Championship", "Mens Championship")
        event_entries[event].append(entry)

# output
line_separator = "\n"
with open("output.txt", "w") as file_out:
    for event in sorted(event_entries.iterkeys()):
        # format unique entries
        entries = set()
        if "Team Maneuver" in event:
            for entry in event_entries[event]:
                university = entry["University"].strip()
                entries.add(university + "\t" + university)
        else:
            for entry in event_entries[event]:
                university = entry["University"].strip()
                skater = entry["First Name"].strip() + " " + entry["Last Name"].strip()
                entries.add(skater + "\t" + university)
        # write data
        file_out.write(event)
        file_out.write(line_separator)
        for entry in sorted(entries):
            file_out.write(entry)
            file_out.write(line_separator)
        file_out.write(line_separator)  # need blank line between events?
