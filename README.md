# heuristicscheduler

A heuristic approach to assigning students to courses, with additional constraints

## Algorithm

1. Calculate each student's "happiness score". This can be used to represent constraints and preferences. In our case, students need at least one course in each of five categories to graduate. This is represented by giving these students -1000 in their happiness score. If students already have courses allocated, give them happiness points, with most if they have their first choice, fewer for second choice etc.

2. Take the student with the lowest happiness score. Attempt to allocate a course to them, trying their highest preference first.

3. Go to 1 to re-evaluate happiness scores.
