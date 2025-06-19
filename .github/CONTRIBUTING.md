# Contribution Guidelines

First of all, thank you for your interest in the project.

Regardless of whether you are thinking about creating an issue or opening a pull request, I truly appreciate the help.
Without communication, I cannot know what the community wants, what they use or how they use it.
Pull requests and issues are exactly what gives me the visibility I need, so thank you.

## Getting started

While following the exact process is neither mandatory nor enforced, it is recommended to try following it as it may help avoid wasted efforts.

### Creating an issue

Whether you have a **question**, found a **bug**, would like to see a **new feature** added or anything along those lines, creating an issue is
going to be the first step. The issue templates will help guide you, but simply creating an issue with the reason for the creation
of said issue is perfectly fine.

Furthermore, if you don't want to fix the problem or implement the feature yourself, that's completely fine.
Creating an issue alone will give both the maintainers as well as the other members of the community visibility on said issue,
which is a lot more likely to get the issue resolved than if the problem/request was left untold.

### Solving an issue

Looking to contribute? Awesome! Look through the open issues in the repository, preferably those that are already labelled.

If you found one that interests you, try to make sure nobody's already working on it.
Adding a comment to the issue asking the maintainer if you can tackle it is a perfectly acceptable way of doing that!

If there's no issue yet for what you want to solve, start by [Creating an issue](#creating-an-issue), specify
you'd like to take a shot at solving it, and finally, wait for the maintainer to comment on the issue.

You don't _have_ to wait for the maintainer to comment on the issue before starting to work on it if you're sure that there's no other
similar existing issues, open or closed, but if the maintainer has commented, it means the maintainer has, based on the comment itself,
acknowledged the issue.

## Commits

All commits are expected to follow the conventional commits specification.

```
<type>[scope]: <description>
```

It's not a really big deal if you don't, but the commits in your PR might be squashed into a single commit
with the appropriate format at the reviewer's discretion.

Here's a few examples of good commit messages:

- `feat(api): add endpoint to retrieve images`
- `fix: remove bad parameter from Slack alerting provider`
- `test(security): add tests for basic auth with bcrypt`
- `docs: add paragraph on running the application locally`
