import { userData as bobUserData } from "./repos";

const ACCOUNTS_KEY = "aivcs.accounts.v1";
const SESSION_KEY = "aivcs.session.v1";

const clone = (value) => JSON.parse(JSON.stringify(value));

function getSeedAccounts() {
  const bobData = clone(bobUserData);
  delete bobData.password;

  return [
    {
      email: "bob@example.com",
      password: "bob-password",
      username: "bob",
      userData: bobData,
    },
    {
      email: "alice@example.com",
      password: "alice-password",
      username: "alice",
      userData: {
        email: "alice@example.com",
        username: "alice",
        createdAt: "2026-09-24T13:00:00+00:00",
        noOfRepositories: 1,
        noOfCommits: 0,
        repositories: [
          {
            repositoryId: "alice-playground",
            repositoryName: "playground",
            description: "Alice's demo repository",
            branches: [{ branchName: "main", headCommitId: null, commits: [] }],
          },
        ],
      },
    },
  ];
}

export function loadAccounts() {
  let accounts = [];
  try {
    const storedAccounts = localStorage.getItem(ACCOUNTS_KEY);
    const parsedAccounts = storedAccounts ? JSON.parse(storedAccounts) : [];
    accounts = Array.isArray(parsedAccounts) ? parsedAccounts : [];
  } catch {
    accounts = [];
  }

  for (const seedAccount of getSeedAccounts()) {
    if (
      !accounts.some(
        (account) => account.email.toLowerCase() === seedAccount.email,
      )
    ) {
      accounts.push(seedAccount);
    }
  }
  saveAccounts(accounts);
  return accounts;
}

export function saveAccounts(accounts) {
  localStorage.setItem(ACCOUNTS_KEY, JSON.stringify(accounts));
}

export function getSignedInAccount() {
  const accounts = loadAccounts();
  try {
    const session = JSON.parse(localStorage.getItem(SESSION_KEY) ?? "null");
    if (!session?.email || !session?.password) return null;

    const account = accounts.find(
      (item) =>
        item.email === session.email && item.password === session.password,
    );
    if (account) return account;
  } catch {
    // Invalid session data falls back to the login screen.
  }
  localStorage.removeItem(SESSION_KEY);
  return null;
}

export function storeSession(account) {
  localStorage.setItem(
    SESSION_KEY,
    JSON.stringify({ email: account.email, password: account.password }),
  );
}

export function clearSession() {
  localStorage.removeItem(SESSION_KEY);
}

export function persistUserData(email, userData) {
  const accounts = loadAccounts().map((account) =>
    account.email === email ? { ...account, userData } : account,
  );
  saveAccounts(accounts);
}
