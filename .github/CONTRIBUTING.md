# Contributing

When contributing to this repository, please first discuss the change you wish to make with the owners of this repository by creating an issue before making a change. 

## Pull Request Process

1. Create a Fork of the project to your own repository.
1. Create a Branch in your Fork.
3. Do the changes in your Branch.
3. Add a Test that checks the change you did. This is done by adding a test function to the test file: `pulp/tests/test_pulp.py` (the function needs to start with `test_`). 
4. If you have added a new solver API, please provide instructions on how to obtain the solver and, in case it's a commercial solver, also how to get a test or academic license to test the API ourselves.
5. Create some bigger problems in a separate file where you can time the solution process to see if you are making changes that are more efficient, also use CProfile can help.
6. Create a Pull Request (PR) when you're done so we can review it.
6. In case your contribution consists on new functionality, an update on the docs would also be appropriate.
7. You will be kindly asked to sign a Contributor License Agreement by a COIN-OR sponsored bot before merging your changes.

## Want to contribute but do not know where to start?

Check the [Roadmap][roadmap] for the project to see what you can help with. We're always looking for more examples and better documentation.

### Attribution

This Code of Conduct is adapted from the [Contributor Covenant][homepage], version 1.4,
available at [http://contributor-covenant.org/version/1/4][version]

[homepage]: http://contributor-covenant.org
[version]: http://contributor-covenant.org/version/1/4/
[roadmap]: https://github.com/coin-or/pulp/projects/1
