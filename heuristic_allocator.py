from collections import Counter, deque
from itertools import chain
from random import shuffle, choice
from matplotlib import pyplot as plt
import seaborn as sns
import sys

import argparse

import numpy as np
import pandas as pd

PREF_POINTS = {
    1: 25,
    2: 18,
    3: 15,
    4: 12,
    5: 10,
    6: 8,
    7: 6,
    8: 4,
    9: 2,
    10: 1,
    11: 0,
    12: 0,
    13: 0,
    14: 0,
    15: 0,
    16: 0,
}
GROUP_NEEDED_HAPPINESS = -1000
MAX_OPTIONS = 6

def calc_student_happiness(idx, students, groups):
    happiness = 0
    for pref, value in PREF_POINTS.items():
        if students.loc[idx, f"got_{pref}"]:
            happiness += value
    if students.loc[idx, "year"] == "Y4":
        for group in groups["name"]:
            if not students.loc[idx, group]:
                happiness += GROUP_NEEDED_HAPPINESS
    students.loc[idx, "happiness"] = happiness

def next_student(students):
    unallocated = students.loc[students["allocated"] < students["ncourses"], :]
    min_happy = unallocated["happiness"].min()
    try:
        return choice(unallocated.loc[unallocated["happiness"] == min_happy].index)
    except IndexError: # none left
        return None

def load_and_prepare(student_file, course_file, coursegroup_file):

    students = pd.read_csv(student_file, index_col="name")
    courses = pd.read_csv(course_file, index_col="name")
    coursegroups = pd.read_csv(coursegroup_file)
    groups = pd.DataFrame(
        {"name": list(set(coursegroups["group"]))}
    )

    course_ids = set(courses.index)

    for pref in range(1,len(course_ids)+1):
        students[pref] = ""
        students[f"got_{pref}"] = False

    for idx, row in students.iterrows():
        for course_id in course_ids:
            # set up pref -> course columns
            students.loc[idx, students.loc[idx, course_id]] = course_id

    # student happiness increases as prefs are satisfied
    students["happiness"] = 0
    for idx in students.index:
        calc_student_happiness(idx, students, groups)

    return {
        "students": students,
        "courses": courses,
        "groups": groups,
        "coursegroups": coursegroups
    }

def courses_got(students, course_ids, st_idx):
    result = set()
    student = students.loc[st_idx,:]
    for pref in range(1,len(course_ids)+1):
        if student[f"got_{pref}"]:
            result.add(student[pref])
    return result

def y4_incomplete(students, groups):
    group_ids = list(groups["name"])
    # ids for students where not all requirements are met
    y4 = students.loc[students["year"] == "Y4", :]
    result = y4.index[np.logical_not(np.all(y4.loc[:,group_ids],axis=1))]
    return result

def groups_needed(groups, idx, students):
    result = {
        g for g in groups["name"]
        if not students.loc[idx, g]
    }
    return result

def alloc1(students, courses, groups, coursegroups):
    # simple allocation
    # iteratively loop through all students in random order
    # allocating next available allowed pref
    course_ids = set(courses.index)

    courses_full = set()

    # "bump count" -- how many times did we fail to allocate due to capacity?
    bump = {c: 0 for c in course_ids}

    # weighting score so those who get 1st pref are less likely to get second etc.
    students["allocated"] = 0

    # keep track of number allocated
    courses["allocated"] = 0

    cgdict = {
        c: set(coursegroups.loc[coursegroups["course"] == c].group)
        for c in course_ids
    }

    while True:
        idx = next_student(students)
        if not idx:
            break
        needed = groups_needed(groups, idx, students)
        pref_allocated = False
        for pref in range(1,len(course_ids)+1):
            if students.loc[idx,f"got_{pref}"]:
                continue # already got this one!
            course = students.loc[idx, pref]
            if students.loc[idx, "happiness"] < 0 and not (cgdict[course] & needed):
                # no intersection between groups for this course, and needed groups
                continue
            if course in courses_full:
                bump[course] += 1
                continue # course full!
            # will this one break a semester limit? If so skip
            got = courses_got(students, course_ids, idx)
            semester = courses.loc[course, "semester"]
            semester_totals = Counter(courses.loc[c, "semester"] for c in got)
            if semester_totals[semester] + 1 > students.loc[idx, f"sem{semester}limit"]:
                continue
            # now allocate
            students.loc[idx, f"got_{pref}"] = True
            students.loc[idx, "allocated"] += 1
            courses.loc[course, "allocated"] += 1
            # allocate coursegroups
            students.loc[idx, cgdict[course]] = True
            if courses.loc[course, "allocated"] == courses.loc[course, "capacity"]:
                courses_full.add(course)
            # recalc happiness for student
            calc_student_happiness(idx, students, groups)
            pref_allocated = True
            break
        if not pref_allocated:
            # something bad happened!
            # break and write out what we've got
            print("ouch! couldn't allocate enough places")
            break


    return students, courses, bump

def courseformat_row(row):
    idx = 1
    for c in row.index:
        if type(c) == type("") and c.startswith("got_") and row[c]:
            row[f"courses{idx}"] = row[int(c[4:])]
            idx += 1
    for jdx in range(idx,MAX_OPTIONS+1):
        row[f"courses{jdx}"] = ""
    row["uun"] = row.name.split()[0]
    row["fullname"] = " ".join(row.name.split()[1:])
    return row

def courseformat(students):
    return students.apply(courseformat_row, axis=1)

def gotnreport(students, _prefnumbers, max_got):
    # count % of students who have got at least m of given list
    prefnumbers = list(_prefnumbers)
    got_cols = [f"got_{x}" for x in prefnumbers]
    n_prefs = students.loc[:, got_cols]
    got_n = n_prefs.sum(axis=1)
    return {
        m: (got_n >= m).sum()*100/students.shape[0]
        for m in range(max_got,0,-1)
    }

def choicehist(students, course, limit):
    # how many students had this course as their 1st, 2nd, 3rd choice?
    return [
        (students[course] == rank).sum()
        for rank in range(1,limit+1)
    ]

def report(students, courses, bump, out_file):
    course_ids = set(courses.index)

    limit = 5
    xlabels = ["1st","2nd","3rd","4th","5th"]
    fig, axes = plt.subplots(4,4,figsize=(20,20))
    axes=axes.flatten()
    choice_histograms = {
        course: choicehist(students, course, limit)
        for course in course_ids
    }
    choice_max = max(chain(*choice_histograms.values()))
    for idx, course in enumerate(course_ids):
        data = pd.DataFrame({
            "x": xlabels,
            "y": choice_histograms[course]
        })
        # plot histogram of top 5 choices
        sns.barplot(x="x", y="y", data=data, ax=axes[idx])
        axes[idx].set_title(course)
        axes[idx].set_xlabel("")
        axes[idx].set_ylabel("")
        axes[idx].set_ylim(0,choice_max)
    fig.savefig("coursehist.png")

    report_file = open("report.txt","w")
    def report(t):
        report_file.write(t+"\n")
        print(t)

    # evaluate ....
    report(
        "course allocations: \n"
        + ',\n'.join(
            f'{course}: {courses.loc[course, "allocated"]}/{courses.loc[course, "capacity"]}'
            for course in course_ids
        )
    )

    def prefreport(pref):
        prefsum = students.loc[:, f'got_{pref}'].sum()
        return f'pref {pref}: {prefsum}/{students.shape[0]}'

    calloc_sum = courses.loc[:, "allocated"].sum()
    salloc_sum = students.loc[:, "allocated"].sum()
    got_cols = (f'got_{pref}' for pref in range(1, len(course_ids)+1))
    gotalloc_sum = students.loc[:, got_cols].to_numpy(dtype=np.bool).flatten().sum()
    needed = int(students.loc[:, "ncourses"].sum())


    report(f"sum of allocations: course {calloc_sum}, student  {salloc_sum}, got {gotalloc_sum}, needed {needed}")

    report(
        "number who got: "
        + ', '.join(
            prefreport(pref)
            for pref in range(1, len(course_ids) + 1)
        )
    )

    report(
        "bumps:\n"
        + ',\n'.join(f"{c}: {bump[c]}" for c in course_ids)
    )

    report(
        "got N of top 3: "
        +', '.join(
            f"{k}: {v:.0f}%"
            for k, v in gotnreport(students, range(1,4), 3).items()
        )
    )

    students.to_csv(out_file)

    report(
        "got N of pref 10 or lower: "
        +', '.join(
            f"{k}: {v:.0f}%"
            for k, v in gotnreport(students, range(10, len(course_ids)+1), 3).items()
        )
    )

    report(
        "got N of pref 10 or lower (Y4): "
        +', '.join(
            f"{k}: {v:.0f}%"
            for k, v in gotnreport(students[students["year"] == "Y4"], range(10, len(course_ids)+1), 3).items()
        )
    )

    h = students["happiness"]
    report(
        f"Happiness mean {h.mean():.1f}, std {h.std():.1f}, (min, max) ({h.min()}, {h.max()})"
    )
    f = plt.figure()
    sns.distplot(
        students["happiness"],
        bins=h.max()-h.min(),
        kde=False
    )

    report(
        "Students with incomplete allocations:\n"
        +"\n".join(students[students["ncourses"] != students["allocated"]].index)
        +"\n\n"
    )

    students["Y4incomplete"] = np.sum(students.loc[:,list(groups["name"])],axis=1)
    report(
        "Y4 students who don't have all BPS groups:\n"
        +"\n".join(y4_incomplete(students,groups))
        +"\n\n"
    )

    report(
        "Students with incomplete allocations:\n"
        +"\n".join(students[students["ncourses"] != students["allocated"]].index)
        +"\n\n"
    )

    plt.xlabel("happiness")
    plt.ylabel("N students")
    plt.savefig("happiness.png")


parser = argparse.ArgumentParser(
    description="Heuristic course allocator for 3rd and 4th year Psychology courses"
)
parser.add_argument("--students", required=True)
parser.add_argument("--courses", required=True)
parser.add_argument("--coursegroups", required=True)
parser.add_argument("--out", required=True)
args = vars(parser.parse_args())


data = load_and_prepare(
    args["students"],
    args["courses"],
    args["coursegroups"]
)
students, courses, groups, coursegroups = (
    data["students"],
    data["courses"],
    data["groups"],
    data["coursegroups"]
)

# do allocation
students, courses, bump = alloc1(students, courses, groups, coursegroups)
students = courseformat(students)
report(students, courses, bump, args["out"])
