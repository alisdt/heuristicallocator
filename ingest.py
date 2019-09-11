import sys
from pathlib import Path
import pandas as pd
import re
import numpy as np
import math

USAGE = """
USAGE: python ingest.py input_filename past_choices_filename output_filename
"""

COURSE_COL_HEADER_RE = r".*preference - (.*) \(Semester.*"

OPTIONAL_WEIGHTING_HEADER = """\
As you need to take 3 Optional Honours courses, how would you like to split your options across the year?
Please note you won't be allocated more than 2 optional courses in a single semester."""

OPTIONAL_HEADER = """\
How many Optional Psychology courses are you going to take in 2019/20?
Each Optional Honours course is worth 20 credits."""

CHOICES_NAMES = ['Biological','Cognitive','Developmental','Differential','Social']

# start with some standard renames
renames = {
    "Please enter your matriculation number": "matric",
    "Please enter your name": "name",
    "Please select your degree type": "degree_type",
    "Please select which year of study you are entering in September": "year",
    "Are you taking the Outreach Course?": "outreach",
    OPTIONAL_HEADER: "optional",
    OPTIONAL_WEIGHTING_HEADER: "semweight"
}

try:
    in_path, past_choices_path, out_path = [Path(x) for x in sys.argv[1:]]
    if not in_path.is_file() or not past_choices_path.is_file():
        raise FileNotFoundError("Can't find one of the input files: "+", ".join(sys.argv[1:]))
    if out_path.exists():
        raise FileExistsError("Output path exists: "+out_path)
except:
    sys.stderr.write(USAGE)
    raise

in_df = pd.read_csv(in_path, header=1, skiprows=[2])
in_df["Start Date"] = pd.to_datetime(in_df["Start Date"], format="%d/%m/%Y %H:%M") # 27/05/2019 16:21

# drop anything that's not completed
in_df = in_df.loc[in_df["Progress"] == 100, :]

in_df = in_df.sort_values("Start Date")
choices_df = pd.read_csv(
    past_choices_path,
    index_col="Username"
)

# unmangle course names
course_cols = set()
for col in in_df.columns:
    m = re.match(COURSE_COL_HEADER_RE, col, re.DOTALL)
    if m is None:
        continue
    renames[col] = m.group(1)
    course_cols.add(m.group(1))

in_df = in_df.rename(renames, axis='columns')

# Map 3rd year / 4th year
in_df = in_df.replace(
    {
        'year':
        {
            "3rd year": "Y3",
            "4th year": "Y4"
        }
    }
)

# blank out NaNs in year so they can be treated as strings
in_df["year"] = in_df["year"].fillna("")

# add number of courses to choose
in_df["ncourses"] = 3 # generally 3, but ....
in_df.loc[
    (in_df["degree_type"] == "Psychology (Single honours)") & (in_df["outreach"] == "Yes"),
    "ncourses"
] = 2 # 2 if taking outreach
in_df.loc[in_df["optional"].notna(),"ncourses"] = in_df.loc[in_df["optional"].notna(),"optional"]

#in_df.to_csv('test1.csv')

records = {}

skip, dup = 0, 0

def convert_choice(c):
    # empty means area has been covered, which should be True
    if c == "" or type(c) == float and math.isnan(c):
        return True
    return False

for idx in in_df.index:
    row = in_df.loc[idx,:]
    orig_id = str(row['matric'])
    id = orig_id.lower().strip()
    if not id.startswith('s'):
        id = 's'+id
    if not len(id) == 8 or not id[1:].isdigit():
        print("Skipping row for invalid matric number: "+orig_id)
        skip += 1
        continue
    no_choices = False
    try:
        choices = {
            k: convert_choice(v)
            for k,v in
            choices_df.loc[id,CHOICES_NAMES].to_dict().items()
        }
    except KeyError:
        no_choices = True
        choices = {x: False for x in CHOICES_NAMES}
    courses = row[course_cols].to_dict()
    # have we got a full set of prefs?
    if set(courses.values()) != set(range(1,len(courses)+1)):
        print(f"Bad prefs for {id}: {str(list(courses.values()))}")
        continue
    if id in records:
        dup += 1
        #print("Warning: overwriting record for "+id)
    # limits for semester 1 / 2
    sem1limit, sem2limit = 2, 2
    if row["semweight"] == "More courses in Semester 1":
        sem2limit = 1
    if row["semweight"] == "More courses in Semester 2":
        sem1limit = 1
    year = row['year']
    if 'honours' not in row['degree_type'].lower():
        year = "" # year irrelevant -> don't do BPS criteria
    if row['ncourses'] > 4:
        sem1limit += 1
        sem2limit += 1
    records[id] = {
        'name': id+" "+row['name'],
        'year': year,
        'ncourses': row['ncourses'],
        'degree_type': row['degree_type'],
        'sem1limit': sem1limit,
        'sem2limit': sem2limit
    }
    records[id].update(choices)
    records[id].update(courses)

print(f"total: {len(in_df.index)}, skipped: {skip}, duplicated: {dup}")


cols_order = ['name', 'year', 'ncourses', 'degree_type','sem1limit','sem2limit']
cols_order += CHOICES_NAMES+list(course_cols)

to_save_df = pd.DataFrame(records.values())

# intify course prefs
for col in course_cols:
    to_save_df[col] = to_save_df[col].fillna(0).astype(int)
to_save_df["ncourses"] = to_save_df["ncourses"].astype(int)
to_save_df.to_csv(out_path, index=None, columns=cols_order)