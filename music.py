#!/usr/bin/python
import csv
import datetime
import eyed3  # mp3 tag editor
import os
import re
import shutil
import subprocess
import urllib
import urlparse
from collections import defaultdict

use_cached_spreadsheet = True
directory = os.path.abspath("data")
download_start_index = 200
download_end_index = 1000


def download_music(url, filename, title, album):
    music_path = os.path.join(directory, "music", filename + ".mp3")
    if os.path.exists(music_path):
        print "Overriding music for " + filename

    parsed_url = urlparse.urlparse(url)
    if parsed_url.netloc == "drive.google.com":
        query_params = urlparse.parse_qs(parsed_url.query)
        url = "https://drive.google.com/uc?export=download&id=" + query_params["id"][0]

    print "Downloading music for " + filename + " from " + url
    (download_path, headers) = urllib.urlretrieve(url)

    original_filename = None
    for disposition in headers["Content-Disposition"].split(";"):
        disposition_parts = disposition.split("=")
        if len(disposition_parts) == 2 and disposition_parts[0] == "filename":
            original_filename = disposition_parts[1].strip("\"")

    file_extension = os.path.splitext(original_filename)[1]
    if file_extension.lower() == ".mp3":
        shutil.copy(download_path, music_path)
    elif file_extension.lower() == ".cda":
        print "Error: Received link rather than music"
        return False
    else:
        if file_extension.lower() not in [".wav", ".m4a", ".aif", ".aiff", ".wma", ".mp2"]:
            print "Warning unusual filetype " + file_extension
        print "Converting from " + file_extension
        subprocess.call(["ffmpeg", "-y", "-i", download_path, "-acodec", "mp3", "-ab", "256k", music_path])

    mp3_file = eyed3.load(music_path)
    if not mp3_file:
        print "Error: cannot open mp3 " + str(mp3_file)
        return False
    if mp3_file.tag:
        mp3_file.tag.clear()
    else:
        mp3_file.initTag()
    mp3_file.tag.title = unicode(title)
    mp3_file.tag.album = unicode(album)
    mp3_file.tag.save(music_path)
    return True


def read_time(filename):
    music_path = os.path.join(directory, "music", filename + ".mp3")
    if not os.path.exists(music_path):
        print "Error: file not found " + music_path
        return 0
    mp3_file = eyed3.load(music_path)
    if not mp3_file:
        print "Error: cannot open mp3 " + str(mp3_file)
        return 0
    return mp3_file.info.time_secs


def normalize_event_name(entry):
    if entry["Gender"] == "Male":
        gender = "Mens"
    else:
        gender = "Ladies"
    event = entry["Event"].title().strip()
    level = event.split()[0]
    if "Short" in event:
        return level + " " + gender + " Short"
    elif "Free" in event:
        return level + " " + gender + " Free"
    elif "Championship" in event:
        return level + " Championship " + gender + " Free"


def read_entries():
    entries = defaultdict(list)  # event -> entry
    with open(os.path.join(directory, "entries.csv"), "r") as file_in:
        reader = csv.DictReader(file_in)
        for entry in reader:
            event = normalize_event_name(entry)
            if event:
                entries[event].append(entry)
    return entries


def generate_report():
    with open("template.html", "r") as template, open(os.path.join(directory, "music", "index.html"), "w") as file_out:
        for row in template:
            if row == "<!--CONTENT-->\n":
                for event in sorted(event_entries.iterkeys()):
                    file_out.write("<h2>" + event + "</h2>\n")
                    file_out.write("<table>\n")
                    file_out.write("<tr>\n")
                    file_out.write("<th>Skater</th>\n")
                    file_out.write("<th>University</th>\n")
                    file_out.write("<th>Music Length</th>\n")
                    file_out.write("<th>Music</th>\n")
                    file_out.write("</tr>\n")

                    for entry in sorted(event_entries[event], key=lambda e: e["full_name"]):
                        university = entry["University"].strip()
                        scratch = entry["Scratch"]
                        skater = entry["full_name"]
                        music_length = ""
                        music = ""
                        if "music_length" in entry and entry["music_length"] > 0:
                            music_length = str(datetime.timedelta(seconds=entry["music_length"]))[3:]
                            music = "<a href=" + entry["music_filename"] + ".mp3>mp3</a>"
                        if scratch:
                            file_out.write("<tr class='scratch'>\n")
                        else:
                            file_out.write("<tr>\n")
                        file_out.write("<td>" + skater + "</td>\n")
                        file_out.write("<td>" + university + "</td>\n")
                        file_out.write("<td>" + music_length + "</td>\n")
                        file_out.write("<td>" + music + "</td>\n")
                        file_out.write("</tr>\n")

                    file_out.write("</table>\n")
            else:
                file_out.write(row)


def match_skater(name, event):
    entries = event_entries[event]
    best_match = None
    best_score = 0
    for entry in entries:
        score = 0
        first_name = entry["First Name"].strip().title()
        last_name = entry["Last Name"].strip().title()
        name_parts = name.split()
        first_name_form = name_parts[0]
        last_name_form = name_parts[-1]
        if last_name_form == last_name:
            score += 2
        if first_name_form == first_name:
            score += 2
        if last_name in name:
            score += 4
        if last_name[0] == name.split()[-1][0]:
            score += 1
        if first_name in name:
            score += 2
        if first_name[0] == name[0]:
            score += 1
        if score > best_score:
            best_match = entry
            best_score = score
    if best_score < 4:
        print "Failed to match skater " + name
        return None
    return best_match


def process_music(name, email, event, url, download):
    entry = match_skater(name, event)
    if entry:
        registered_name = entry["First Name"].strip() + " " + entry["Last Name"].strip()
        music_filename = event + "__" + registered_name
        music_filename = re.sub(r"\W+", "_", music_filename)

        # store extra data
        entry["original_music_url"] = url
        entry["music_submission_name"] = name
        entry["music_submission_email"] = email
        entry["normalized_event"] = event
        entry["registered_name"] = registered_name
        entry["music_filename"] = music_filename

        if download:
            download_music(url, music_filename, registered_name, event)


############
# WORKFLOW #
############

# Read Entries
event_entries = read_entries()

# Download Spreadsheet
input_spreadsheet_path = os.path.join(directory, "input.csv")
if os.path.exists(input_spreadsheet_path) and use_cached_spreadsheet:
    print "Using cached spreadsheet"
else:
    print "Downloading live spreadsheet"
    key_path = os.path.join(directory, "key.txt")
    with open(key_path, "r") as key_file:
        spreadsheet_key = key_file.read().strip()
    music_spreadsheet_url = "https://docs.google.com/spreadsheets/d/" + spreadsheet_key + "/export?format=csv"
    urllib.urlretrieve(music_spreadsheet_url, input_spreadsheet_path)

# Parse data
with open(input_spreadsheet_path, "r") as file_in:
    reader = csv.DictReader(file_in)
    for i, row in enumerate(reader):
        download = download_start_index < i < download_end_index
        name = row["Name"].strip().title()
        email = row["Email Address"].strip()
        free_event = row["Free Skate Event"]
        free_url = row["Free Skate Music Upload"]
        short_event = row["Short Program Event"]
        short_url = row["Short Program Music Upload"]

        if free_url:
            if free_event:
                process_music(name, email, free_event, free_url, download)
            else:
                print "Invalid free submission " + name
        if short_url:
            if short_event:
                process_music(name, email, short_event, short_url, download)
            else:
                print "Invalid short submission " + name


# Read music lengths
for event in event_entries:
    for entry in event_entries[event]:
        entry["full_name"] = entry["First Name"].strip() + " " + entry["Last Name"].strip()
        if "music_filename" in entry:
            entry["music_length"] = read_time(entry["music_filename"])

generate_report()
