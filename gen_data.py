from copy import copy
from random import choice, choices, sample, randrange, random, shuffle

import pandas as pd

#### course file with
# course, semester, popularity, capacity

#### course group file with
# course, group
# can have more than one entry per course (in multiple groups)

#### student file with
# student ID, number of courses taken, column per course with pref (none indicates don't want)
# popularity is a proportion used to weight choices

SEED = 42
N_COURSES = 16
N_GROUPS = 6
CAPACITY_ALL = 50
N_STUDENTS = 250
COURSES_PER_YEAR = 3

def gen_groups():
    return [
        {'name': f'G{x:02d}'}
        for x in range(1, N_GROUPS+1)
    ]

def gen_courses_equal():
    result = [
        {
            'name': f'C{x:02d}',
            'semester': choice([1, 2]),
            'popularity': 1.0,
            'capacity': CAPACITY_ALL,
            'area': 'stuff'
        }
        for x in range(1, N_COURSES + 1)
    ]
    return result


AREAS = {
    'social': {'n_courses': 5, 'randslice': (0, 0.75)},
    'clinical': {'n_courses': 5, 'randslice': (0.75, 0.95)}
}

def gen_courses_areas():
    names = set(f'C{x:02d}' for x in range(1, N_COURSES+1))
    semesters = [1, 2]*(1+N_COURSES//2)
    shuffle(semesters)
    result = {
        name : {
            'name': name,
            'semester': semesters.pop(),
            'popularity': 1.0,
            'capacity': CAPACITY_ALL,
            'area': 'stuff'
        }
        for name in names
    }
    # running copy of all names to make sure we don't reuse courses
    names_running = copy(names)
    for k, v in AREAS.items():
        AREAS[k]['set'] = set(sample(names_running, v['n_courses']))
        names_running -= AREAS[k]['set']
        for course in AREAS[k]['set']:
            result[course]['area'] = k
    return list(result.values())

THREE_BAND_N_POPULAR = 5
THREE_BAND_N_UNPOPULAR = 5

def gen_courses_three_band():
    names = set(f'C{x:02d}' for x in range(1, N_COURSES+1))
    popular = set(sample(names, THREE_BAND_N_POPULAR))
    unpopular = set(sample(names-popular, THREE_BAND_N_UNPOPULAR))
    result = []
    for name in names:
        popularity = 1.0
        if name in popular:
            popularity = 3.0
        elif name in unpopular:
            popularity = 0.3
        result.append(
            {
                'name': name,
                'semester': choice([1, 2]),
                'popularity': popularity,
                'capacity': CAPACITY_ALL,
                'area': 'stuff'
            }
        )
    return result

def gen_course_groups(courses, groups):
    return [
        { 'course': c["name"], 'group': g["name"] }
        for c in courses
        for g in sample(groups, 2)
    ]

_rankings_list = list(range(1,N_COURSES+1))

def make_prefs_uniform(student, courses):
    course_names, course_weights = zip(*[(c["name"], c["popularity"]) for c in courses])
    course_names, course_weights = list(course_names), list(course_weights)
    for pref in range(1, N_COURSES+1):
        course = choices(course_names, weights=course_weights, k=1)[0]
        student[course] = pref
        idx = course_names.index(course)
        del course_names[idx]
        del course_weights[idx]
    return student

def make_prefs_areas(student, courses):
    course_names = [c["name"] for c in courses]
    area_r = random()
    prefs = [None]*N_COURSES
    for k, v in AREAS.items():
        lb, ub = v['randslice']
        if lb <= area_r < ub:
            # area chosen!
            prefs[:3] = sample(list(AREAS[k]['set']), 3)
            break
    for idx, pref in enumerate(prefs):
        if pref is None:
            ch = choice(course_names)
            while ch in prefs:
                ch = choice(course_names)
            prefs[idx] = ch
    # add prefs to student record
    for course_name in course_names:
        student[course_name] = prefs.index(course_name)+1
    return student

def gen_student(n, courses, groups, course_alloc):
    result = {
        'name': f'S{n:03d}',
        'ncourses': COURSES_PER_YEAR,
        'year': choice(['Y3', 'Y4'])
    }
    result.update({g["name"]: False for g in groups})
    if result["year"] == "Y4":
        # assume at least 2 groups have been covered, up to
        # twice the number of courses per year
        n_groups = randrange(3, COURSES_PER_YEAR*2+1)
        for group in sample(groups, n_groups):
            result[group["name"]] = True
    r = random()
    result['sem1limit'], result['sem2limit'] = 2, 2
    if r < 0.25:
        result['sem1limit'] = 1
    elif r < 0.5:
        result['sem2limit'] = 1
    result = course_alloc(result, courses)
    return result

def gen_students(courses, groups, course_alloc):
    return [gen_student(n, courses, groups, course_alloc) for n in range(1, N_STUDENTS+1)]

groups_list = gen_groups()
courses_list = gen_courses_areas()
students_list = gen_students(courses_list, groups_list, make_prefs_areas)
course_groups_list = gen_course_groups(courses_list, groups_list)
pd.DataFrame(groups_list).to_csv('groups.csv', index=None)
pd.DataFrame(courses_list).to_csv('testcourses.csv', index=None)
pd.DataFrame(course_groups_list).to_csv('testcoursegroups.csv', index=None)
pd.DataFrame(students_list).to_csv('teststudents.csv', index=None)