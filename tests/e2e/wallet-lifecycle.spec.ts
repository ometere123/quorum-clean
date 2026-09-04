import { test, expect, type Page } from "@playwright/test";

/**
 * Exercises the actual application wallet path against a realistic mocked EIP-1193 provider,
 * installed before the page loads so `window.ethereum` is present at first render the same way a
 * real extension's content script is. Nothing here talks to StudioNet: these tests are about the
 * wallet state machine and error surfacing, not contract execution.
 *
 * `eth_accounts` defaults to an empty array. A fresh, never-authorized origin gets `[]` back from
 * a real wallet, and the app's own passive-discovery effect (`wallet-provider.tsx`) treats a
 * non-empty answer as silent proof of a prior connection — so a mock that always answers with a
 * real address auto-connects the app before any test explicitly clicks anything, which is also
 * what a first version of this spec got wrong: `getByRole("button", { name: "Connect wallet" })`
 * without `exact: true` substring-matches "Disconnect wallet" too (it contains "connect wallet"),
 * so an auto-connected page's Connect-wallet locator silently resolved to the Disconnect button
 * instead and every assertion after it failed for the wrong reason. Every button lookup below is
 * `exact: true` for that reason, not style.
 *
 * The provider records every method it was asked for, which is what lets `no Snap RPC method is
 * ever called` be a real assertion rather than an absence of evidence: if `client.connect()` (the
 * genlayer-js helper this app deliberately stopped calling) were ever reintroduced, this would
 * catch it by seeing `wallet_getSnaps` in the call log.
 */

type MockOptions = {
  chainId?: string;
  accounts?: string[];
  /** Answered by eth_accounts on passive discovery. Empty by default; see module doc. */
  preAuthorizedAccounts?: string[];
  failMethod?: { method: string; error: unknown };
};

async function installMockWallet(page: Page, options: MockOptions = {}) {
  await page.addInitScript(
    ({ chainId, accounts, preAuthorizedAccounts, failMethod }) => {
      const state = {
        chainId: chainId ?? "0xf22f",
        accounts: accounts ?? ["0x000000000000000000000000000000000000aa"],
        preAuthorized: preAuthorizedAccounts ?? [],
      };
      const listeners: Record<string, ((...args: unknown[]) => void)[]> = {};
      const calls: string[] = [];

      (window as unknown as { __walletCalls: string[] }).__walletCalls = calls;
      (window as unknown as { __mockWalletEmit: (event: string, arg: unknown) => void }).__mockWalletEmit = (
        event,
        arg,
      ) => {
        for (const listener of listeners[event] ?? []) listener(arg);
      };

      (window as unknown as { ethereum: unknown }).ethereum = {
        request: async ({ method }: { method: string }) => {
          calls.push(method);
          if (failMethod && method === failMethod.method) {
            throw failMethod.error;
          }
          switch (method) {
            case "eth_chainId":
              return state.chainId;
            case "eth_accounts":
              return state.preAuthorized;
            case "eth_requestAccounts":
              return state.accounts;
            case "wallet_switchEthereumChain":
              state.chainId = "0xf22f";
              // A real wallet emits chainChanged after a switch; the app's switchNetwork()
              // deliberately does not re-poll and relies on that event to learn the new chain.
              for (const listener of listeners["chainChanged"] ?? []) listener(state.chainId);
              return null;
            case "wallet_getSnaps":
            case "wallet_requestSnaps":
            case "wallet_invokeSnap":
              // A real wallet without the GenLayer snap throws here. The app must never call
              // these at all now, so if it does, answering "installed" would silently hide that
              // regression instead of the call log catching it.
              throw { code: -32601, message: `method [${method}] doesn't has corresponding handler` };
            default:
              throw { code: -32601, message: `method [${method}] doesn't has corresponding handler` };
          }
        },
        on: (event: string, listener: (...args: unknown[]) => void) => {
          (listeners[event] ??= []).push(listener);
        },
        removeListener: (event: string, listener: (...args: unknown[]) => void) => {
          listeners[event] = (listeners[event] ?? []).filter((l) => l !== listener);
        },
      };
    },
    {
      chainId: options.chainId,
      accounts: options.accounts,
      preAuthorizedAccounts: options.preAuthorizedAccounts,
      failMethod: options.failMethod,
    },
  );
}

const walletCalls = (page: Page) => page.evaluate(() => (window as unknown as { __walletCalls: string[] }).__walletCalls);
const emit = (page: Page, event: string, arg: unknown) =>
  page.evaluate(({ event, arg }) => (window as unknown as { __mockWalletEmit: (e: string, a: unknown) => void }).__mockWalletEmit(event, arg), { event, arg });

const connectButton = (page: Page) => page.getByRole("button", { name: "Connect wallet", exact: true });
const disconnectButton = (page: Page) => page.getByRole("button", { name: "Disconnect wallet", exact: true });
const switchNetworkButton = (page: Page) => page.getByRole("button", { name: "Switch network", exact: true });

test.describe("Wallet lifecycle against a mocked injected provider", () => {
  test("detects the provider, connects, and shows the account and recognised chain", async ({ page }) => {
    await installMockWallet(page);
    await page.goto("/");
    await expect(page.getByText("No injected wallet was found in this browser.")).toHaveCount(0);

    await connectButton(page).click();
    await expect(page.getByText("0x0000…00aa")).toBeVisible();
    await expect(page.locator(".qc-masthead").getByText("studionet", { exact: true })).toBeVisible();
    await expect(disconnectButton(page)).toBeVisible();

    const calls = await walletCalls(page);
    expect(calls).toContain("eth_requestAccounts");
    expect(calls).not.toContain("wallet_getSnaps");
    expect(calls).not.toContain("wallet_requestSnaps");
    expect(calls).not.toContain("wallet_invokeSnap");
  });

  test("passive discovery silently restores a previously-authorized session on page load, with no click", async ({ page }) => {
    await installMockWallet(page, { preAuthorizedAccounts: ["0x000000000000000000000000000000000000aa"] });
    await page.goto("/");
    await expect(page.getByText("0x0000…00aa")).toBeVisible();
    await expect(disconnectButton(page)).toBeVisible();
    await expect(connectButton(page)).toHaveCount(0);
  });

  test("a wallet on the wrong chain is recognised and blocked, then switch-network recovers it", async ({ page }) => {
    await installMockWallet(page, { chainId: "0x1" }); // ethereum mainnet, not studionet
    await page.goto("/");
    await connectButton(page).click();

    await expect(page.getByText("wrong network: chain 1")).toBeVisible();
    await expect(switchNetworkButton(page)).toBeVisible();

    await switchNetworkButton(page).click();
    await expect(page.locator(".qc-masthead").getByText("studionet", { exact: true })).toBeVisible();
    await expect(switchNetworkButton(page)).toHaveCount(0);
  });

  test("accountsChanged and chainChanged events update the UI live", async ({ page }) => {
    await installMockWallet(page);
    await page.goto("/");
    await connectButton(page).click();
    await expect(page.getByText("0x0000…00aa")).toBeVisible();

    await emit(page, "accountsChanged", ["0x00000000000000000000000000000000000bbb"]);
    await expect(page.getByText("0x0000…0bbb")).toBeVisible();

    await emit(page, "chainChanged", "0x1");
    await expect(page.getByText("wrong network: chain 1")).toBeVisible();
  });

  test("an empty accountsChanged and a disconnect event both clear the session", async ({ page }) => {
    await installMockWallet(page);
    await page.goto("/");
    await connectButton(page).click();
    await expect(disconnectButton(page)).toBeVisible();

    await emit(page, "accountsChanged", []);
    await expect(connectButton(page)).toBeVisible();

    await connectButton(page).click();
    await expect(disconnectButton(page)).toBeVisible();
    await emit(page, "disconnect", { message: "provider closed" });
    await expect(connectButton(page)).toBeVisible();
  });

  test("clicking Disconnect wallet clears the session locally", async ({ page }) => {
    await installMockWallet(page);
    await page.goto("/");
    await connectButton(page).click();
    await expect(disconnectButton(page)).toBeVisible();

    await disconnectButton(page).click();
    await expect(connectButton(page)).toBeVisible();
  });

  test("a structured provider/RPC error object renders as real text, never [object Object]", async ({ page }) => {
    await installMockWallet(page, {
      failMethod: {
        method: "eth_requestAccounts",
        error: { code: -32002, message: "Request already pending, please check your wallet." },
      },
    });
    await page.goto("/");
    await connectButton(page).click();

    await expect(page.getByText("Request already pending, please check your wallet.")).toBeVisible();
    await expect(page.getByText("[object Object]")).toHaveCount(0);
  });

  test("a wallet rejection (code 4001) reads as a calm cancellation, not a crash", async ({ page }) => {
    await installMockWallet(page, {
      failMethod: { method: "eth_requestAccounts", error: { code: 4001, message: "User rejected the request." } },
    });
    await page.goto("/");
    await connectButton(page).click();

    await expect(page.getByText("Transaction rejected in wallet.")).toBeVisible();
    await expect(page.getByText("[object Object]")).toHaveCount(0);
  });

  test("Register Participant reaches the real write path without ever probing for a Snap", async ({ page }) => {
    await installMockWallet(page);
    await page.goto("/rounds");
    // Fixture-mode rounds are seeded; open the first one's participants tab and submit.
    const openRound = page.getByRole("link", { name: /Open round/ }).first();
    await openRound.click();
    await page.getByRole("link", { name: "Participants" }).click();

    await connectButton(page).click();
    await expect(disconnectButton(page)).toBeVisible();

    await page.getByPlaceholder("Human-readable label").fill("e2e mock write-path check");
    await page.getByRole("button", { name: "register participant" }).click();

    // Fixture mode has no CONTRACT_ADDRESS, so the write path's own configured-contract guard is
    // the next thing to fire — proving the flow reached the real write call at all, with no Snap
    // probe in between, rather than dying on [object Object] before it got there.
    await expect(page.getByText("The canonical contract is not configured.")).toBeVisible();
    await expect(page.getByText("[object Object]")).toHaveCount(0);

    const calls = await walletCalls(page);
    expect(calls).not.toContain("wallet_getSnaps");
    expect(calls).not.toContain("wallet_requestSnaps");
    expect(calls).not.toContain("wallet_invokeSnap");
  });
});
