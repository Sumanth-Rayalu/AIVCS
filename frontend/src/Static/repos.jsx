export const userData = {
  email: "bob@example.com",
  username: "bob",
  password: "bob-password",
  createdAt: "2026-09-24T13:00:00+00:00",
  noOfRepositories: 1,
  noOfCommits: 1,
  repositories: [
    {
      repositoryId: "demo",
      repositoryName: "AIVCS-project",
      description: "AIVCS project repository",
      branches: [
        {
          branchName: "main",
          headCommitId: "bob-main-001",
          commits: [
            {
              commitId: "bob-main-001",
              message: "Initial commit",
              timestamp: "2026-09-24T13:05:00+00:00",
              author: "bob",
              parent: null,
              fileDetails: [
                {
                  filename: "README",
                  fileextension: ".md",
                  content: "# Bob's project",
                  contentHash: "hash-bob-main",
                },
              ],
            },
            {
              commitId: "bob-main-002",
              message: "Added main.py",
              timestamp: "2026-09-24T13:10:00+00:00",
              author: "bob",
              parent: "bob-main-001",
              fileDetails: [
                {
                  filename: "main",
                  fileextension: ".py",
                  content: "print('Hello, World!')",
                  contentHash: "hash-bob-main-002",
                },
              ],
            },
          ],
        },
        {
          branchName: "feature-branch",
          headCommitId: "bob-feature-001",
          commits: [
            {
              commitId: "bob-feature-001",
              message: "Initial commit on feature branch",
              timestamp: "2026-09-24T13:20:00+00:00",
              author: "bob",
              parent: null,
              fileDetails: [
                {
                  filename: "feature.py",
                  fileextension: ".py",
                  content: "print('Feature implementation')",
                  contentHash: "hash-bob-feature-001",
                },
              ],
            },
          ],
        },
      ],
    },
    {
      repositoryId: "demo2",
      repositoryName: "AIVCS-project-2",
      description: "AIVCS project repository 2",
      branches: [
        {
          branchName: "main",
          headCommitId: "bob-main-003",
          commits: [
            {
              commitId: "bob-main-003",
              message: "Initial commit for repo 2",
              timestamp: "2026-09-24T13:15:00+00:00",
              author: "bob",
              parent: null,
              fileDetails: [
                {
                  filename: "README",
                  fileextension: ".md",
                  content: "# Bob's project 2",
                  contentHash: "hash-bob-main-003",
                },
              ],
            },
          ],
        },
      ],
    },
  ],
};
