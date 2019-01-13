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

directory = os.path.abspath("data")

##############
# DATA MODEL #
##############


class Event(object):

    def __init__(self, level, gender, category, min_music_length, max_music_length):
        self.level = level
        self.gender = gender
        self.category = category
        self.min_music_length = min_music_length
        self.max_music_length = max_music_length
        # back-references
        self.starts = []
        # computed properties
        self.name = level
        if gender == "Female":
            self.name += " Ladies "
        elif gender == "Male":
            self.name += " Mens "
        else:
            self.name += " "
        self.name += category
        self.short_name = self.level + " " + self.category.replace("Solo ", "")
        self.has_submitted_music = (self.max_music_length > 0)

    def __repr__(self):
        return str(self)

    def __str__(self):
        return "Event: {}".format(self.name)


class Skater(object):

    def __init__(self, usfs_number, first_name, last_name, email):
        self.usfs_number = usfs_number
        self.first_name = first_name
        self.last_name = last_name
        self.email = email
        # back-references
        self.starts = []
        # computed properties
        self.full_name = "{} {}".format(self.first_name, self.last_name)

    def __repr__(self):
        return str(self)

    def __str__(self):
        return "Skater: {} {} {}".format(self.full_name, self.usfs_number, self.email)


class Skaters(object):

    def __init__(self):
        self.skaters = []
        self.skaters_by_usfs = {}
        self.skaters_by_name = {}
        self.skaters_by_email = {}

    def find_or_create(self, usfs_number, first_name, last_name, email):
        if usfs_number == "0" or usfs_number == "none":
            usfs_number = ""
        full_name = first_name + " " + last_name
        skater = self.find(usfs_number, full_name, email)
        if not skater:
            skater = Skater(usfs_number, first_name, last_name, email)
            self.skaters.append(skater)
            self.skaters_by_usfs[usfs_number] = skater
            self.skaters_by_name[full_name] = skater
            self.skaters_by_email[email] = skater
        return skater

    def find(self, usfs_number, name, email):
        if usfs_number and usfs_number in self.skaters_by_usfs and self.skaters_by_usfs[usfs_number].last_name in name:
            skater = self.skaters_by_usfs[usfs_number]
        elif name and name in self.skaters_by_name:
            skater = self.skaters_by_name[name]
            print ("Warning matching skater by name", name, email, usfs_number, skater)
        elif email and email in self.skaters_by_email:
            skater = self.skaters_by_email[email]
            print ("Warning matching skater by email", name, email, usfs_number, skater)
        else:
            skater = None
        return skater


class Start(object):

    def __init__(self, skater, event):
        self.skater = skater
        self.event = event
        self.last_music_submission = None
        self.music_key = re.sub(r"\W+", "_", event.name + "  " + skater.full_name)
        skater.starts.append(self)
        event.starts.append(self)

    def __repr__(self):
        return str(self)

    def __str__(self):
        return "Start: {} {}".format(self.event, self.skater.full_name)


class MusicSubmission(object):

    def __init__(self, skater, event, url, index):
        self.skater = skater
        self.event = event
        self.url = url
        self.index = index

    def __repr__(self):
        return str(self)

    def __str__(self):
        return "Submission: {} {} {} {}".format(self.skater, self.event, self.url, self.index)


##################
# READING INPUTS #
##################


def int_or_zero(s):
    if not s:
        return 0
    return int(s)


def read_events():
    events = []
    with open("events.csv", "r") as file_in:
        reader = csv.DictReader(file_in)
        for row in reader:
            event = Event(
                level=row["Level"],
                gender=row["Gender"],
                category=row["Category"],
                min_music_length=int_or_zero(row["Min Music Length"]),
                max_music_length=int_or_zero(row["Max Music Length"])
            )
            events.append(event)
    return events


def find_start_for_skater(event, skater):
    for start in skater.starts:
        if event == start.event.short_name:
            return start
    else:
        print ("Warning cannot find start", event, skater.starts)


def create_submission(skater, event_name, url, index,):
    submission = MusicSubmission(skater, event_name, url, index)
    start = find_start_for_skater(event_name, skater)
    if start:
        start.last_music_submission = submission
    return submission


def read_submissions(skaters):
    submissions = []
    with open(os.path.join(directory, "input.csv"), "r") as file_in:
        reader = csv.DictReader(file_in)
        for i, row in enumerate(reader):
            usfs_number = row["USFS Number"]
            name = row["Skater Name"].strip().title()
            email = row["Email Address"].strip()
            skater = skaters.find(usfs_number, name, email)
            if skater:
                free_dance_event = row["Free Dance Event"]
                free_dance_url = row["Free Dance Music"]
                free_skate_event = row["Free Skate Event"]
                free_skate_url = row["Free Skate Music"]
                short_event = row["Short Program Event"]
                short_url = row["Short Program Music"]

                if free_dance_event and free_dance_url:
                    submissions.append(create_submission(skater, free_dance_event, free_dance_url, i))
                if free_skate_event and free_skate_url:
                    submissions.append(create_submission(skater, free_skate_event, free_skate_url, i))
                if short_event and short_url:
                    submissions.append(create_submission(skater, short_event, short_url, i))
            else:
                print ("Warning cannot find skater", name, email, usfs_number)
    return submissions


def get_cached_music(start, subdir):
    prefix = str(start.last_music_submission.index) + "_" + start.music_key
    for file_name in os.listdir(os.path.join(directory, subdir)):
        if os.path.splitext(file_name)[0] == prefix:
            return file_name
    return None


def download_music(start):
    # TODO use google drive API
    submission = start.last_music_submission
    if submission and not get_cached_music(start, "music_raw"):
        url = submission.url
        parsed_url = urlparse.urlparse(submission.url)
        if parsed_url.netloc == "drive.google.com":
            query_params = urlparse.parse_qs(parsed_url.query)
            url = "https://drive.google.com/uc?export=download&id=" + query_params["id"][0]

        print "Downloading music from " + url
        (download_path, headers) = urllib.urlretrieve(url)

        original_filename = None
        for disposition in headers["Content-Disposition"].split(";"):
            disposition_parts = disposition.split("=")
            if len(disposition_parts) == 2 and disposition_parts[0] == "filename":
                original_filename = disposition_parts[1].strip("\"")

        file_extension = os.path.splitext(original_filename)[1]
        music_filename = str(submission.index) + "_" + start.music_key + file_extension
        music_path = os.path.join(directory, "music_raw", music_filename)
        if os.path.exists(music_path):
            print "Overriding music for " + music_filename
        shutil.copy(download_path, music_path)


def convert_music(start):
    submission = start.last_music_submission
    if submission:
        input_file_name = get_cached_music(start, "music_raw")
        if input_file_name:
            input_path = os.path.join(directory, "music_raw", input_file_name)
            output_path = os.path.join(directory, "music", start.music_key + ".mp3")
            # TODO smart overriding for not os.path.exists(output_path)
            title = start.skater.full_name
            album = start.event.name
            file_extension = os.path.splitext(input_file_name)[1]
            if file_extension.lower() in [".mp3", ".wav", ".m4a", ".aif", ".aiff", ".wma", ".mp2"]:
                print ("Converting", input_file_name)
                subprocess.call(["ffmpeg", "-y", "-i", input_path, "-acodec", "mp3", "-ab", "256k", output_path])
            else:
                print ("Unknown music format", input_file_name)
                return

            mp3_file = eyed3.load(output_path)
            if not mp3_file:
                print "Error: cannot open mp3 " + str(mp3_file)
                return False
            if mp3_file.tag:
                mp3_file.tag.clear()
            else:
                mp3_file.initTag()
            mp3_file.tag.title = unicode(title)
            mp3_file.tag.album = unicode(album)
            mp3_file.tag.save(output_path)


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


# convert entries spreadsheet to events spreadsheet format
def normalize_event_name(entry):
    event = entry["Event"].title().strip()
    if "(Male)" in event:
        event = event.replace(" (Male)", "")
        male_event = True
    elif "(Men)" in event:
        event = event.replace(" (Men)", "")
        male_event = True
    else:
        male_event = False

    if "Short Program" in event:
        level = event.split()[0]
        if male_event:
            assert entry["Gender"] == "Male"
            return level + " Mens Short Program"
        else:
            assert entry["Gender"] == "Female"
            return level + " Ladies Short Program"
    elif "Excel" in event or "Championship" in event:
        if male_event:
            assert entry["Gender"] == "Male"
            return event + " Mens Freeskate"
        else:
            assert entry["Gender"] == "Female"
            return event + " Ladies Freeskate"
    elif "Pattern Dance" in event:
        return event.replace("Pattern Dance", "Solo Pattern Dance")
    else:  # Team Maneuvers or Solo Free Dance
        return event


def read_entries(events_by_name):
    starts = []
    skaters = Skaters()
    with open(os.path.join(directory, "entries.csv"), "r") as file_in:
        reader = csv.DictReader(file_in)
        for row in reader:
            event = events_by_name[normalize_event_name(row)]
            usfs_number = row["USF #"].strip()
            first_name = row["First Name"].strip().title()
            last_name = row["Last Name"].strip().title()
            email = row["E-mail"].strip()
            skater = skaters.find_or_create(usfs_number, first_name, last_name, email)
            start = Start(skater, event)
            starts.append(start)
    return starts, skaters


def generate_report(event_entries):
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


def debug_skater(skaters, name):
    skater = skaters.find("", name, "")
    print(skater)
    print(skater.starts)
    for start in skater.starts:
        print start.last_music_submission


############
# WORKFLOW #
############

def main():

    # read events
    events = read_events()
    events_by_name = {event.name: event for event in events}

    # read entries
    starts, skaters = read_entries(events_by_name)

    # TODO use to google sheets api
    # # Download Spreadsheet
    # if os.path.exists(os.path.join(directory, "input.csv")) and use_cached_spreadsheet:
    #     print "Using cached spreadsheet"
    # else:
    #     print "Downloading live spreadsheet"
    #     key_path = os.path.join(directory, "key.txt")
    #     with open(key_path, "r") as key_file:
    #         spreadsheet_key = key_file.read().strip()
    #     music_spreadsheet_url = "https://docs.google.com/spreadsheets/d/" + spreadsheet_key + "/export?format=csv"
    #     urllib.urlretrieve(music_spreadsheet_url, input_spreadsheet_path)

    # read submissions
    submissions = read_submissions(skaters)

    for start in starts:
        # download music files
        download_music(start)
        # convert music to mp3
        # convert_music(start)

    # TODO migrate
    # # Read music lengths
    # for event in event_entries:
    #     for entry in event_entries[event]:
    #         entry["full_name"] = entry["First Name"].strip() + " " + entry["Last Name"].strip()
    #         if "music_filename" in entry:
    #             entry["music_length"] = read_time(entry["music_filename"])
    #


    # generate_report(event_entries)


if __name__ == "__main__":
    main()
