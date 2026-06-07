"use client";

import { useEffect, useMemo, useState } from "react";
import { ethers } from "ethers";

import {
  FAITH_TOKEN_ABI,
  FAITH_TOKEN_ADDRESS,
  FUSD_ABI,
  FUSD_ADDRESS,
  MOCK_ORACLE_ABI,
  MOCK_ORACLE_ADDRESS,
  VAULT_MANAGER_ABI,
  VAULT_MANAGER_ADDRESS,
  FAUCET_ABI,
  FAUCET_ADDRESS,
} from "@/lib/contracts";

declare global {
  interface Window {
    ethereum?: any;
  }
}

type DemoProgress = {
  claim: boolean;
  deposit: boolean;
  borrow: boolean;
  crash: boolean;
  liquidation: boolean;
};

type ActivityItem = {
  id: string;
  type: "Deposit" | "Withdraw" | "Borrow" | "Repay" | "Liquidation" | "Oracle";
  title: string;
  description: string;
  blockNumber: number;
  txHash: string;
  user?: string;
  liquidator?: string;
  amount?: number;
  debtRepaid?: number;
  collateralSeized?: number;
  previousPrice?: number;
  newPrice?: number;
};

const DEPLOYMENT_BLOCK = 19416324;
const DEMO_PROGRESS_STORAGE_KEY = "faith-demo-progress-v3";
const MEGAETH_CHAIN_ID_DECIMAL = 6343;
const MEGAETH_CHAIN_ID_HEX = "0x18c7";

const DEFAULT_DEMO_PROGRESS: DemoProgress = {
  claim: false,
  deposit: false,
  borrow: false,
  crash: false,
  liquidation: false,
};

export default function Home() {
  const [wallet, setWallet] = useState("");
  const [walletProvider, setWalletProvider] = useState<any>(null);
  const [faithBalance, setFaithBalance] = useState("0");
  const [fusdBalance, setFusdBalance] = useState("0");
  const [collateral, setCollateral] = useState("0");
  const [debt, setDebt] = useState("0");
  const [vaultActive, setVaultActive] = useState(false);
  const [healthFactor, setHealthFactor] = useState("∞");
  const [borrowLimit, setBorrowLimit] = useState("0");
  const [availableBorrow, setAvailableBorrow] = useState("0");
  const [oraclePrice, setOraclePrice] = useState("1");
  const [protocolCollateral, setProtocolCollateral] = useState("0");
  const [protocolDebtSupply, setProtocolDebtSupply] = useState("0");

  const [depositAmount, setDepositAmount] = useState("");
  const [borrowAmount, setBorrowAmount] = useState("");
  const [repayAmount, setRepayAmount] = useState("");
  const [withdrawAmount, setWithdrawAmount] = useState("");
  const [liquidateAddress, setLiquidateAddress] = useState("");
  const [newPrice, setNewPrice] = useState("");

  const [activity, setActivity] = useState<ActivityItem[]>([]);
  const [activityLoading, setActivityLoading] = useState(false);
  const [demoProgress, setDemoProgress] = useState<DemoProgress>(DEFAULT_DEMO_PROGRESS);
  const [status, setStatus] = useState("");

  const healthNumber = healthFactor === "∞" ? Number.POSITIVE_INFINITY : Number(healthFactor);

  useEffect(() => {
    const saved = window.localStorage.getItem(DEMO_PROGRESS_STORAGE_KEY);
    if (saved) {
      try {
        setDemoProgress({ ...DEFAULT_DEMO_PROGRESS, ...JSON.parse(saved) });
      } catch {
        setDemoProgress(DEFAULT_DEMO_PROGRESS);
      }
    }
  }, []);

  useEffect(() => {
    const activeProvider = walletProvider || window.ethereum;
    if (!activeProvider) return;

    const handleAccountsChanged = (accounts: string[]) => {
      const nextWallet = accounts?.[0] || "";
      setWallet(nextWallet);
      if (nextWallet) refreshEverything(nextWallet, activeProvider);
    };

    const handleChainChanged = () => window.location.reload();

    activeProvider.on?.("accountsChanged", handleAccountsChanged);
    activeProvider.on?.("chainChanged", handleChainChanged);

    return () => {
      activeProvider.removeListener?.("accountsChanged", handleAccountsChanged);
      activeProvider.removeListener?.("chainChanged", handleChainChanged);
    };
  }, [walletProvider]);

  useEffect(() => {
    if (wallet) refreshEverything(wallet);
  }, [wallet, walletProvider]);

  const riskStatus = useMemo(() => {
    if (healthFactor === "∞") {
      return { label: "No Debt", color: "text-sky-300", bg: "bg-sky-500/10", border: "border-sky-500/30" };
    }
    if (healthNumber < 1.1) {
      return { label: "Liquidatable", color: "text-red-300", bg: "bg-red-500/10", border: "border-red-500/30" };
    }
    if (healthNumber < 1.5) {
      return { label: "Warning", color: "text-orange-300", bg: "bg-orange-500/10", border: "border-orange-500/30" };
    }
    return { label: "Healthy", color: "text-green-300", bg: "bg-green-500/10", border: "border-green-500/30" };
  }, [healthFactor, healthNumber]);

  const demoSteps = [
    {
      number: "01",
      title: "Claim 1000 tFAITH",
      description: "Use the FAITH faucet to claim test collateral tokens for the live MegaETH demo.",
      complete: demoProgress.claim,
    },
    {
      number: "02",
      title: "Deposit 10 tFAITH",
      description: "Create collateral inside the tVaultManager and activate a borrower position.",
      complete: demoProgress.deposit,
    },
    {
      number: "03",
      title: "Borrow 5 tfUSD",
      description: "Mint test credit against tFAITH collateral while respecting the 60% borrow limit.",
      complete: demoProgress.borrow,
    },
    {
      number: "04",
      title: "Crash tFAITH to $0.40",
      description: "Use the test oracle to simulate a rapid market shock and create liquidation risk.",
      complete: demoProgress.crash,
    },
    {
      number: "05",
      title: "Liquidate unsafe tVault",
      description: "Clear bad debt and seize collateral when the health factor falls below the liquidation threshold.",
      complete: demoProgress.liquidation,
    },
  ];

  const completedDemoSteps = demoSteps.filter((step) => step.complete).length;

  const recommendedAction = useMemo(() => {
    if (!wallet) return "Connect your wallet to begin the live demo.";
    if (!demoProgress.claim) return "Next: Claim 1000 tFAITH from the faucet.";
    if (!demoProgress.deposit) return "Next: Deposit 10 tFAITH.";
    if (!demoProgress.borrow) return "Next: Borrow 5 tfUSD.";
    if (!demoProgress.crash) return "Next: Crash tFAITH price to $0.40.";
    if (!demoProgress.liquidation) return "Next: Liquidate the unsafe tVault.";
    return "Demo completed successfully ✔";
  }, [wallet, demoProgress]);

  function shortAddress(address: string) {
    return `${address.slice(0, 6)}...${address.slice(-4)}`;
  }

  function shortHash(hash: string) {
    return `${hash.slice(0, 8)}...${hash.slice(-6)}`;
  }

  function updateDemoProgress(update: Partial<DemoProgress>) {
    const next = { ...demoProgress, ...update };
    setDemoProgress(next);
    window.localStorage.setItem(DEMO_PROGRESS_STORAGE_KEY, JSON.stringify(next));
  }

  async function switchToMegaETH(activeProvider: any) {
    if (!activeProvider?.request) throw new Error("Wallet provider not found");

    try {
      await activeProvider.request({
        method: "wallet_switchEthereumChain",
        params: [{ chainId: MEGAETH_CHAIN_ID_HEX }],
      });
    } catch (switchError: any) {
      if (switchError?.code === 4902) {
        await activeProvider.request({
          method: "wallet_addEthereumChain",
          params: [
            {
              chainId: MEGAETH_CHAIN_ID_HEX,
              chainName: "MegaETH Testnet",
              nativeCurrency: { name: "ETH", symbol: "ETH", decimals: 18 },
              rpcUrls: ["https://carrot.megaeth.com/rpc"],
              blockExplorerUrls: [],
            },
          ],
        });
      } else {
        throw switchError;
      }
    }
  }

  async function createWalletConnectProvider() {
    const projectId = process.env.NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID;

    if (!projectId) {
      throw new Error("Missing NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID");
    }

    const EthereumProvider = (
      await import("@walletconnect/ethereum-provider")
    ).default;

    const provider = await EthereumProvider.init({
      projectId,
      chains: [MEGAETH_CHAIN_ID_DECIMAL],
      optionalChains: [MEGAETH_CHAIN_ID_DECIMAL],
      rpcMap: {
        [MEGAETH_CHAIN_ID_DECIMAL]: "https://carrot.megaeth.com/rpc",
      },
      showQrModal: true,
      methods: [
        "eth_sendTransaction",
        "eth_signTransaction",
        "eth_sign",
        "personal_sign",
        "eth_signTypedData",
        "wallet_switchEthereumChain",
        "wallet_addEthereumChain",
      ],
      events: ["chainChanged", "accountsChanged", "disconnect"],
      metadata: {
        name: "FAITH Protocol",
        description: "MegaETH testnet collateralized credit demo",
        url: typeof window !== "undefined" ? window.location.origin : "https://faith-protocol-mvp.vercel.app",
        icons: [],
      },
    });

    await provider.connect({ chains: [MEGAETH_CHAIN_ID_DECIMAL] });
    return provider;
  }

  async function getActiveProvider() {
    return walletProvider || window.ethereum || null;
  }

  async function ensureMegaETHProvider(providerOverride?: any) {
    const activeProvider = providerOverride || (await getActiveProvider());
    if (!activeProvider) throw new Error("Wallet not detected");

    try {
      await switchToMegaETH(activeProvider);
    } catch (error) {
      console.warn("Network switch request failed or was not supported", error);
    }

    const provider = new ethers.BrowserProvider(activeProvider);
    const network = await provider.getNetwork();
    if (Number(network.chainId) !== MEGAETH_CHAIN_ID_DECIMAL) {
      throw new Error("Wrong network");
    }
    return provider;
  }

  async function loadData(address: string, providerOverride?: any) {
    try {
      const activeProvider = providerOverride || (await getActiveProvider());
      if (!activeProvider) return;
      const provider = new ethers.BrowserProvider(activeProvider);
      const network = await provider.getNetwork();
      if (Number(network.chainId) !== MEGAETH_CHAIN_ID_DECIMAL) {
        setStatus("Please switch to MegaETH Testnet to load live protocol data.");
        return;
      }

      const faith = new ethers.Contract(FAITH_TOKEN_ADDRESS, FAITH_TOKEN_ABI, provider);
      const fusd = new ethers.Contract(FUSD_ADDRESS, FUSD_ABI, provider);
      const vault = new ethers.Contract(VAULT_MANAGER_ADDRESS, VAULT_MANAGER_ABI, provider);
      const oracle = new ethers.Contract(MOCK_ORACLE_ADDRESS, MOCK_ORACLE_ABI, provider);

      const [
        userFaithBalance,
        userFusdBalance,
        vaultData,
        borrowLimitRaw,
        healthRaw,
        oraclePriceRaw,
        vaultManagerFaithBalance,
        totalTfUsdSupply,
      ] = await Promise.all([
        faith.balanceOf(address),
        fusd.balanceOf(address),
        vault.vaults(address),
        vault.getBorrowLimit(address),
        vault.getHealthFactor(address),
        oracle.getPrice(),
        faith.balanceOf(VAULT_MANAGER_ADDRESS),
        fusd.totalSupply(),
      ]);

      const formattedFaithBalance = ethers.formatEther(userFaithBalance);
      const formattedFusdBalance = ethers.formatEther(userFusdBalance);
      const formattedCollateral = ethers.formatEther(vaultData.collateralAmount);
      const formattedDebt = ethers.formatEther(vaultData.debtAmount);
      const formattedBorrowLimit = ethers.formatEther(borrowLimitRaw);
      const formattedOraclePrice = ethers.formatEther(oraclePriceRaw);
      const formattedProtocolCollateral = ethers.formatEther(vaultManagerFaithBalance);
      const formattedProtocolDebt = ethers.formatEther(totalTfUsdSupply);
      const available = Number(formattedBorrowLimit) - Number(formattedDebt);

      setFaithBalance(formattedFaithBalance);
      setFusdBalance(formattedFusdBalance);
      setCollateral(formattedCollateral);
      setDebt(formattedDebt);
      setVaultActive(vaultData.active);
      setBorrowLimit(Number(formattedBorrowLimit).toFixed(2));
      setAvailableBorrow(Math.max(available, 0).toFixed(2));
      setOraclePrice(formattedOraclePrice);
      setProtocolCollateral(formattedProtocolCollateral);
      setProtocolDebtSupply(formattedProtocolDebt);
      setHealthFactor(healthRaw === ethers.MaxUint256 ? "∞" : (Number(healthRaw) / 100).toFixed(2));
    } catch (error) {
      console.error(error);
      setStatus("Loading protocol data failed ❌");
    }
  }

  async function loadActivity(providerOverride?: any) {
    try {
      const activeProvider = providerOverride || (await getActiveProvider());
      if (!activeProvider) return;
      setActivityLoading(true);

      const provider = new ethers.BrowserProvider(activeProvider);
      const network = await provider.getNetwork();
      if (Number(network.chainId) !== MEGAETH_CHAIN_ID_DECIMAL) {
        setStatus("Please switch to MegaETH Testnet to load activity.");
        return;
      }

      const vault: any = new ethers.Contract(VAULT_MANAGER_ADDRESS, VAULT_MANAGER_ABI, provider);
      const oracle: any = new ethers.Contract(MOCK_ORACLE_ADDRESS, MOCK_ORACLE_ABI, provider);

      const [depositEvents, withdrawEvents, borrowEvents, repayEvents, liquidationEvents, oracleEvents] = await Promise.all([
        vault.queryFilter(vault.filters.CollateralDeposited(), DEPLOYMENT_BLOCK, "latest"),
        vault.queryFilter(vault.filters.CollateralWithdrawn(), DEPLOYMENT_BLOCK, "latest"),
        vault.queryFilter(vault.filters.TfUSDBorrowed(), DEPLOYMENT_BLOCK, "latest"),
        vault.queryFilter(vault.filters.TfUSDRepaid(), DEPLOYMENT_BLOCK, "latest"),
        vault.queryFilter(vault.filters.VaultLiquidated(), DEPLOYMENT_BLOCK, "latest"),
        oracle.queryFilter(oracle.filters.PriceUpdated(), DEPLOYMENT_BLOCK, "latest"),
      ]);

      const items: ActivityItem[] = [];

      for (const event of depositEvents as any[]) {
        const user = event.args.user;
        const amount = Number(ethers.formatEther(event.args.amount));
        items.push({ id: `${event.transactionHash}-${event.index}`, type: "Deposit", title: "tFAITH Deposited", description: `${shortAddress(user)} deposited ${amount} tFAITH`, blockNumber: event.blockNumber, txHash: event.transactionHash, user, amount });
      }
      for (const event of withdrawEvents as any[]) {
        const user = event.args.user;
        const amount = Number(ethers.formatEther(event.args.amount));
        items.push({ id: `${event.transactionHash}-${event.index}`, type: "Withdraw", title: "tFAITH Withdrawn", description: `${shortAddress(user)} withdrew ${amount} tFAITH`, blockNumber: event.blockNumber, txHash: event.transactionHash, user, amount });
      }
      for (const event of borrowEvents as any[]) {
        const user = event.args.user;
        const amount = Number(ethers.formatEther(event.args.amount));
        items.push({ id: `${event.transactionHash}-${event.index}`, type: "Borrow", title: "tfUSD Borrowed", description: `${shortAddress(user)} borrowed ${amount} tfUSD`, blockNumber: event.blockNumber, txHash: event.transactionHash, user, amount });
      }
      for (const event of repayEvents as any[]) {
        const user = event.args.user;
        const amount = Number(ethers.formatEther(event.args.amount));
        items.push({ id: `${event.transactionHash}-${event.index}`, type: "Repay", title: "tfUSD Repaid", description: `${shortAddress(user)} repaid ${amount} tfUSD`, blockNumber: event.blockNumber, txHash: event.transactionHash, user, amount });
      }
      for (const event of liquidationEvents as any[]) {
        const user = event.args.user;
        const liquidator = event.args.liquidator;
        const debtRepaid = Number(ethers.formatEther(event.args.debtRepaid));
        const collateralSeized = Number(ethers.formatEther(event.args.collateralSeized));
        items.push({ id: `${event.transactionHash}-${event.index}`, type: "Liquidation", title: "tVault Liquidated", description: `${shortAddress(liquidator)} liquidated ${shortAddress(user)} — ${debtRepaid} tfUSD repaid, ${collateralSeized} tFAITH seized`, blockNumber: event.blockNumber, txHash: event.transactionHash, user, liquidator, debtRepaid, collateralSeized });
      }
      for (const event of oracleEvents as any[]) {
        const previousPrice = Number(ethers.formatEther(event.args.previousPrice));
        const newOraclePrice = Number(ethers.formatEther(event.args.newPrice));
        items.push({ id: `${event.transactionHash}-${event.index}`, type: "Oracle", title: "tMockOracle Updated", description: `tFAITH price changed from $${previousPrice} to $${newOraclePrice}`, blockNumber: event.blockNumber, txHash: event.transactionHash, previousPrice, newPrice: newOraclePrice });
      }

      items.sort((a, b) => b.blockNumber - a.blockNumber);
      setActivity(items.slice(0, 50));
    } catch (error) {
      console.error(error);
      setStatus("Loading on-chain activity failed ❌");
    } finally {
      setActivityLoading(false);
    }
  }

  async function refreshEverything(address: string, providerOverride?: any) {
    await Promise.all([loadData(address, providerOverride), loadActivity(providerOverride)]);
  }

  async function connectWallet() {
    try {
      setStatus("Connecting wallet...");

      let activeProvider = window.ethereum || null;

      if (!activeProvider) {
        setStatus("Opening WalletConnect...");
        activeProvider = await createWalletConnectProvider();
      }

      setWalletProvider(activeProvider);
      setStatus("Switching to MegaETH Testnet...");

      const provider = await ensureMegaETHProvider(activeProvider);
      let accounts = await provider.send("eth_requestAccounts", []);

      if (!accounts?.length) {
        accounts = await provider.send("eth_accounts", []);
      }

      if (!accounts?.[0]) {
        throw new Error("No wallet account returned");
      }

      setWallet(accounts[0]);
      setStatus("Wallet connected on MegaETH ✔");
      await refreshEverything(accounts[0], activeProvider);
    } catch (error) {
      console.error(error);
      setStatus("Wallet connection failed ❌ Use MetaMask, Rabby, or WalletConnect and switch to MegaETH Testnet.");
    }
  }

  async function resetDemoFlow() {
    setDemoProgress(DEFAULT_DEMO_PROGRESS);
    window.localStorage.setItem(DEMO_PROGRESS_STORAGE_KEY, JSON.stringify(DEFAULT_DEMO_PROGRESS));
    setStatus("Demo Flow reset to 0/5 ✔");
  }

  async function claimTestFaith() {
    try {
      if (!wallet) return;
      setStatus("Claiming 1000 tFAITH from faucet...");
      const provider = await ensureMegaETHProvider();
      const signer = await provider.getSigner();
      const faucet = new ethers.Contract(FAUCET_ADDRESS, FAUCET_ABI, signer);
      const tx = await faucet.claim();
      await tx.wait();
      updateDemoProgress({ claim: true });
      setStatus("1000 tFAITH claimed successfully ✔");
      await refreshEverything(wallet);
    } catch (error: any) {
      console.error(error);
      const message = String(error?.message || "").toLowerCase();
      if (message.includes("already claimed") || message.includes("execution reverted")) {
        updateDemoProgress({ claim: true });
        setStatus("This wallet already claimed or faucet claim already completed ✔");
        await refreshEverything(wallet);
        return;
      }
      setStatus("Faucet claim failed ❌ Make sure this wallet has MegaETH testnet gas and has not claimed before.");
    }
  }

  async function depositCollateral() {
    try {
      if (!depositAmount || !wallet) return;
      setStatus("Approving tFAITH...");
      const provider = await ensureMegaETHProvider();
      const signer = await provider.getSigner();
      const faith = new ethers.Contract(FAITH_TOKEN_ADDRESS, FAITH_TOKEN_ABI, signer);
      const vault = new ethers.Contract(VAULT_MANAGER_ADDRESS, VAULT_MANAGER_ABI, signer);
      const amount = ethers.parseEther(depositAmount);
      const approveTx = await faith.approve(VAULT_MANAGER_ADDRESS, amount);
      await approveTx.wait();
      setStatus("Depositing tFAITH collateral...");
      const tx = await vault.depositCollateral(amount);
      await tx.wait();
      updateDemoProgress({ deposit: true });
      setStatus("tFAITH deposit successful ✔");
      setDepositAmount("");
      await refreshEverything(wallet);
    } catch (error) {
      console.error(error);
      setStatus("tFAITH deposit failed ❌");
    }
  }

  async function borrowTfUSD() {
    try {
      if (!borrowAmount || !wallet) return;
      setStatus("Borrowing tfUSD...");
      const provider = await ensureMegaETHProvider();
      const signer = await provider.getSigner();
      const vault = new ethers.Contract(VAULT_MANAGER_ADDRESS, VAULT_MANAGER_ABI, signer);
      const tx = await vault.borrow(ethers.parseEther(borrowAmount));
      await tx.wait();
      updateDemoProgress({ borrow: true });
      setStatus("tfUSD borrow successful ✔");
      setBorrowAmount("");
      await refreshEverything(wallet);
    } catch (error) {
      console.error(error);
      setStatus("tfUSD borrow failed ❌");
    }
  }

  async function repayTfUSD() {
    try {
      if (!repayAmount || !wallet) return;
      setStatus("Approving tfUSD...");
      const provider = await ensureMegaETHProvider();
      const signer = await provider.getSigner();
      const fusd = new ethers.Contract(FUSD_ADDRESS, FUSD_ABI, signer);
      const vault = new ethers.Contract(VAULT_MANAGER_ADDRESS, VAULT_MANAGER_ABI, signer);
      const amount = ethers.parseEther(repayAmount);
      const approveTx = await fusd.approve(VAULT_MANAGER_ADDRESS, amount);
      await approveTx.wait();
      setStatus("Repaying tfUSD...");
      const tx = await vault.repay(amount);
      await tx.wait();
      setStatus("tfUSD repayment successful ✔");
      setRepayAmount("");
      await refreshEverything(wallet);
    } catch (error) {
      console.error(error);
      setStatus("tfUSD repayment failed ❌");
    }
  }

  async function withdrawCollateral() {
    try {
      if (!withdrawAmount || !wallet) return;
      setStatus("Withdrawing tFAITH collateral...");
      const provider = await ensureMegaETHProvider();
      const signer = await provider.getSigner();
      const vault = new ethers.Contract(VAULT_MANAGER_ADDRESS, VAULT_MANAGER_ABI, signer);
      const tx = await vault.withdrawCollateral(ethers.parseEther(withdrawAmount));
      await tx.wait();
      setStatus("tFAITH withdrawal successful ✔");
      setWithdrawAmount("");
      await refreshEverything(wallet);
    } catch (error) {
      console.error(error);
      setStatus("tFAITH withdrawal failed ❌");
    }
  }

  async function liquidateVault() {
    try {
      if (!liquidateAddress || !wallet) return;
      setStatus("Reading target tVault debt...");
      const provider = await ensureMegaETHProvider();
      const signer = await provider.getSigner();
      const fusd = new ethers.Contract(FUSD_ADDRESS, FUSD_ABI, signer);
      const vault = new ethers.Contract(VAULT_MANAGER_ADDRESS, VAULT_MANAGER_ABI, signer);
      const targetVault = await vault.vaults(liquidateAddress);
      const targetDebt = targetVault.debtAmount;
      if (targetDebt.toString() === "0") {
        setStatus("Target tVault has no tfUSD debt ❌");
        return;
      }
      setStatus("Approving tfUSD for liquidation...");
      const approveTx = await fusd.approve(VAULT_MANAGER_ADDRESS, targetDebt);
      await approveTx.wait();
      setStatus("Liquidating unsafe tVault...");
      const tx = await vault.liquidate(liquidateAddress);
      await tx.wait();
      updateDemoProgress({ liquidation: true });
      setStatus("tVault liquidation successful ✔");
      setLiquidateAddress("");
      await refreshEverything(wallet);
    } catch (error) {
      console.error(error);
      setStatus("tVault liquidation failed ❌");
    }
  }

  async function setOraclePriceOnchain(price: string) {
    try {
      if (!price || !wallet) return;
      setStatus("Updating tMockOracle price...");
      const provider = await ensureMegaETHProvider();
      const signer = await provider.getSigner();
      const oracle = new ethers.Contract(MOCK_ORACLE_ADDRESS, MOCK_ORACLE_ABI, signer);
      const tx = await oracle.setPrice(ethers.parseEther(price));
      await tx.wait();
      if (Number(price) <= 0.4) updateDemoProgress({ crash: true });
      setStatus("tMockOracle price updated ✔");
      setNewPrice("");
      await refreshEverything(wallet);
    } catch (error) {
      console.error(error);
      setStatus("tMockOracle update failed ❌");
    }
  }

  return (
    <main className="min-h-screen bg-[#050608] p-6 text-white lg:p-8">
      <section className="mb-8 flex flex-col justify-between gap-6 rounded-3xl border border-white/10 bg-white/[0.03] p-8 lg:flex-row lg:items-center">
        <div>
          <div className="mb-3 inline-flex rounded-full border border-blue-500/30 bg-blue-500/10 px-3 py-1 text-sm font-semibold text-blue-300">
            MegaETH Testnet MVP
          </div>
          <h1 className="text-5xl font-bold tracking-tight">FAITH Protocol</h1>
          <p className="mt-3 max-w-2xl text-lg text-zinc-400">
            Real-time collateralized credit on MegaETH with tFAITH collateral, tfUSD borrowing, oracle-based risk simulation, and liquidations.
          </p>
        </div>
        {!wallet ? (
          <button onClick={connectWallet} className="rounded-2xl bg-blue-600 px-8 py-4 text-lg font-bold transition hover:bg-blue-500">
            Connect Wallet
          </button>
        ) : (
          <div className="rounded-2xl border border-white/10 bg-black/30 px-6 py-4">
            <p className="text-sm text-zinc-500">Connected Wallet</p>
            <p className="mt-1 font-semibold text-white">{wallet.slice(0, 6)}...{wallet.slice(-4)}</p>
          </div>
        )}
      </section>

      <section className="mb-8 rounded-3xl border border-amber-500/20 bg-amber-500/[0.06] p-6">
        <div className="mb-3 inline-flex rounded-full border border-amber-400/30 bg-amber-400/10 px-3 py-1 text-sm font-bold text-amber-200">
          Tester Setup Required
        </div>
        <h2 className="text-2xl font-bold">Before testing, get MegaETH testnet gas</h2>
        <p className="mt-2 max-w-4xl text-zinc-300">
          Testers need a small amount of MegaETH testnet ETH to pay gas before claiming tFAITH or using the protocol. The Connect Wallet button supports MetaMask desktop, MetaMask mobile browser, and WalletConnect on mobile Safari/Chrome.
        </p>
        <div className="mt-5 grid gap-4 md:grid-cols-3">
          <SetupCard title="1. Open wallet" body="On mobile Safari/Chrome, use WalletConnect when prompted. MetaMask mobile browser also works." />
          <SetupCard title="2. Get gas" body="Fund the wallet with MegaETH testnet ETH before transactions." />
          <SetupCard title="3. Run demo" body="Claim 1000 tFAITH, deposit, borrow, crash the oracle, and liquidate." />
        </div>
      </section>

      <section className="mb-8 rounded-3xl border border-cyan-500/20 bg-cyan-500/[0.06] p-6">
        <div className="mb-6 flex flex-col justify-between gap-4 lg:flex-row lg:items-center">
          <div>
            <div className="mb-2 inline-flex rounded-full border border-cyan-400/30 bg-cyan-400/10 px-3 py-1 text-sm font-bold text-cyan-200">
              Investor Demo Flow
            </div>
            <h2 className="text-3xl font-bold">Prove the FAITH Protocol loop in 5 on-chain steps</h2>
            <p className="mt-2 max-w-3xl text-zinc-300">This tracker stays complete after liquidation until you reset it.</p>
          </div>
          <div className="flex flex-col gap-3">
            <div className="rounded-2xl border border-white/10 bg-black/30 px-5 py-4">
              <p className="text-sm text-zinc-400">Demo Progress</p>
              <p className="mt-1 text-3xl font-bold text-cyan-200">{completedDemoSteps}/5</p>
            </div>
            <button onClick={resetDemoFlow} className="rounded-2xl border border-cyan-400/20 bg-cyan-400/10 px-5 py-3 text-sm font-bold text-cyan-200 transition hover:bg-cyan-400/20">
              Reset Demo Flow
            </button>
          </div>
        </div>
        <div className="mb-5 rounded-2xl border border-white/10 bg-black/30 p-5">
          <p className="text-sm font-semibold uppercase tracking-wide text-zinc-500">Recommended Next Action</p>
          <p className="mt-2 text-lg font-semibold text-white">{recommendedAction}</p>
          <p className="mt-2 text-sm text-zinc-500">Reset Demo Flow only resets the presentation tracker. It does not change your wallet, balances, or protocol state.</p>
        </div>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
          {demoSteps.map((step) => (
            <DemoStepCard key={step.number} number={step.number} title={step.title} description={step.description} complete={step.complete} />
          ))}
        </div>
      </section>

      <section className="mb-8 rounded-3xl border border-white/10 bg-white/[0.03] p-6">
        <h2 className="text-2xl font-bold">Why FAITH is built for MegaETH</h2>
        <div className="mt-5 grid gap-5 md:grid-cols-3">
          <NarrativeCard title="Real-Time Risk" body="FAITH reacts instantly to collateral price shocks and displays borrower solvency live." />
          <NarrativeCard title="Fast Liquidation" body="Unsafe debt positions can be cleared immediately, reducing stale-state risk in credit markets." />
          <NarrativeCard title="Visible On-Chain Activity" body="Every deposit, borrow, price update, and liquidation is exposed through a transparent activity layer." />
        </div>
      </section>

      <section className="mb-8">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-2xl font-bold">Protocol Overview</h2>
          <div className={`rounded-full border px-4 py-2 text-sm font-bold ${riskStatus.bg} ${riskStatus.border} ${riskStatus.color}`}>
            User Risk Status: {riskStatus.label}
          </div>
        </div>
        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
          <MetricCard label="Total tFAITH Collateral" value={Number(protocolCollateral).toLocaleString()} helper="Held inside tVaultManager" />
          <MetricCard label="Total tfUSD Debt Supply" value={Number(protocolDebtSupply).toLocaleString()} helper="Outstanding test credit" />
          <MetricCard label="tFAITH Oracle Price" value={`$${oraclePrice}`} helper="tMockOracle live value" />
          <MetricCard label="tVault Address" value={`${VAULT_MANAGER_ADDRESS.slice(0, 6)}...${VAULT_MANAGER_ADDRESS.slice(-4)}`} helper="Current test deployment" />
        </div>
      </section>

      <section className="mb-8 rounded-3xl border border-white/10 bg-white/[0.03] p-6">
        <div className="mb-5 flex flex-col justify-between gap-4 lg:flex-row lg:items-center">
          <div>
            <h2 className="text-2xl font-bold">Your tVault</h2>
            <p className="mt-1 text-zinc-400">Live account position and borrowing health.</p>
          </div>
          <div className={`rounded-full border px-4 py-2 text-sm font-bold ${vaultActive ? "border-green-500/30 bg-green-500/10 text-green-300" : "border-zinc-500/30 bg-zinc-500/10 text-zinc-300"}`}>
            {vaultActive ? "Vault Active" : "Vault Inactive"}
          </div>
        </div>
        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-7">
          <MetricCard label="tFAITH Balance" value={Number(faithBalance).toLocaleString()} />
          <MetricCard label="tfUSD Balance" value={Number(fusdBalance).toLocaleString()} />
          <MetricCard label="Collateral" value={collateral} />
          <MetricCard label="Debt" value={debt} />
          <MetricCard label="Borrow Limit" value={borrowLimit} />
          <MetricCard label="Available Borrow" value={availableBorrow} />
          <div className="rounded-3xl border border-white/10 bg-black/30 p-5">
            <p className="text-sm text-zinc-400">Health Factor</p>
            <p className={`mt-3 break-words text-2xl font-bold ${healthFactor !== "∞" && Number(healthFactor) < 1.1 ? "text-red-400" : healthFactor !== "∞" && Number(healthFactor) < 1.5 ? "text-orange-300" : "text-green-400"}`}>{healthFactor}</p>
            <div className="mt-4">
              <div className="h-3 w-full overflow-hidden rounded-full bg-white/10">
                <div className={`h-full transition-all duration-700 ${healthFactor !== "∞" && Number(healthFactor) < 1.1 ? "bg-red-500" : healthFactor !== "∞" && Number(healthFactor) < 1.5 ? "bg-orange-400" : "bg-emerald-400"}`} style={{ width: healthFactor === "∞" ? "100%" : `${Math.min(100, Number(healthFactor) * 50)}%` }} />
              </div>
              <div className="mt-2 flex justify-between text-[10px] font-semibold tracking-wide text-zinc-500">
                <span>DANGER</span><span>WARNING</span><span>SAFE</span>
              </div>
            </div>
            <p className="mt-2 text-xs text-zinc-500">Live solvency monitoring powered by PCSMonitor.</p>
          </div>
        </div>
      </section>

      <section className="mb-8">
        <h2 className="mb-5 text-2xl font-bold">MVP Actions</h2>
        <div className="grid gap-6 lg:grid-cols-2 xl:grid-cols-3">
          <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-6">
            <h3 className="text-2xl font-bold">FAITH Faucet</h3>
            <p className="mt-2 min-h-[48px] text-sm text-zinc-400">Claim 1000 test tFAITH for demo and testing. Each wallet can claim once.</p>
            <button onClick={claimTestFaith} className="mt-5 w-full rounded-2xl bg-cyan-600 p-4 font-bold transition hover:bg-cyan-500">Claim 1000 tFAITH</button>
          </div>
          <ActionCard title="Deposit tFAITH" description="Lock test collateral into your tVault." inputValue={depositAmount} onInputChange={setDepositAmount} placeholder="Amount" buttonLabel="Deposit tFAITH" buttonClassName="bg-green-600 hover:bg-green-500" onClick={depositCollateral} />
          <ActionCard title="Borrow tfUSD" description="Mint tfUSD against available tFAITH collateral." inputValue={borrowAmount} onInputChange={setBorrowAmount} placeholder="Amount" buttonLabel="Borrow tfUSD" buttonClassName="bg-blue-600 hover:bg-blue-500" onClick={borrowTfUSD} />
          <ActionCard title="Repay tfUSD" description="Repay test debt and restore vault health." inputValue={repayAmount} onInputChange={setRepayAmount} placeholder="Amount" buttonLabel="Repay tfUSD" buttonClassName="bg-yellow-600 hover:bg-yellow-500" onClick={repayTfUSD} />
          <ActionCard title="Withdraw tFAITH" description="Withdraw collateral while preserving solvency." inputValue={withdrawAmount} onInputChange={setWithdrawAmount} placeholder="Amount" buttonLabel="Withdraw tFAITH" buttonClassName="bg-red-600 hover:bg-red-500" onClick={withdrawCollateral} />
          <ActionCard title="Liquidate tVault" description="Liquidate an unsafe vault using tfUSD." inputValue={liquidateAddress} onInputChange={setLiquidateAddress} placeholder="User wallet address" buttonLabel="Liquidate tVault" buttonClassName="bg-rose-700 hover:bg-rose-600" onClick={liquidateVault} />
          <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-6">
            <h3 className="text-2xl font-bold">tMockOracle Controls</h3>
            <p className="mt-2 min-h-[48px] text-sm text-zinc-400">Simulate tFAITH price movement and test liquidation behavior.</p>
            <input value={newPrice} onChange={(e) => setNewPrice(e.target.value)} placeholder="New tFAITH price, ex: 0.4" className="mt-5 w-full rounded-2xl border border-white/10 bg-black/30 p-4 outline-none placeholder:text-zinc-600 focus:border-purple-400/70" />
            <div className="mt-4 grid gap-3">
              <button onClick={() => setOraclePriceOnchain(newPrice)} className="w-full rounded-2xl bg-purple-600 p-4 font-bold transition hover:bg-purple-500">Set tFAITH Price</button>
              <button onClick={() => setOraclePriceOnchain("0.4")} className="w-full rounded-2xl bg-orange-600 p-4 font-bold transition hover:bg-orange-500">Crash tFAITH to $0.40</button>
              <button onClick={() => setOraclePriceOnchain("1")} className="w-full rounded-2xl bg-zinc-700 p-4 font-bold transition hover:bg-zinc-600">Reset tFAITH to $1.00</button>
            </div>
          </div>
        </div>
      </section>

      <section className="mb-8 rounded-3xl border border-white/10 bg-white/[0.03] p-6">
        <div className="mb-5 flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
          <div>
            <h2 className="text-2xl font-bold">Recent Protocol Activity</h2>
            <p className="mt-1 text-zinc-400">Live events emitted from tVaultManager and tMockOracle.</p>
          </div>
          <button onClick={loadActivity} className="rounded-2xl border border-white/10 bg-black/30 px-5 py-3 font-semibold transition hover:bg-white/10">{activityLoading ? "Loading..." : "Refresh Activity"}</button>
        </div>
        {activity.length === 0 ? (
          <div className="rounded-2xl border border-white/10 bg-black/30 p-6 text-zinc-400">No protocol activity found yet.</div>
        ) : (
          <div className="space-y-3">{activity.map((item) => <ActivityRow key={item.id} item={item} shortHash={shortHash} />)}</div>
        )}
      </section>

      <section className="rounded-3xl border border-white/10 bg-white/[0.03] p-6">
        <h2 className="text-2xl font-bold">Current Testnet Deployment Registry</h2>
        <div className="mt-5 grid gap-4 text-sm text-zinc-300 lg:grid-cols-2">
          <RegistryLine label="tFAITH" value={FAITH_TOKEN_ADDRESS} />
          <RegistryLine label="tfUSD" value={FUSD_ADDRESS} />
          <RegistryLine label="tMockOracle" value={MOCK_ORACLE_ADDRESS} />
          <RegistryLine label="tVaultManager" value={VAULT_MANAGER_ADDRESS} />
          <RegistryLine label="FaithFaucet" value={FAUCET_ADDRESS} />
        </div>
      </section>

      {status && <div className="mt-8 rounded-3xl border border-white/10 bg-white/[0.03] p-5 text-lg">{status}</div>}
    </main>
  );
}

function MetricCard({ label, value, helper, valueClassName = "text-white" }: { label: string; value: string; helper?: string; valueClassName?: string }) {
  return <div className="rounded-3xl border border-white/10 bg-black/30 p-5"><p className="text-sm text-zinc-400">{label}</p><p className={`mt-3 break-words text-2xl font-bold ${valueClassName}`}>{value}</p>{helper && <p className="mt-2 text-xs text-zinc-500">{helper}</p>}</div>;
}

function DemoStepCard({ number, title, description, complete }: { number: string; title: string; description: string; complete: boolean }) {
  return <div className={`rounded-3xl border p-5 ${complete ? "border-green-500/30 bg-green-500/10" : "border-white/10 bg-black/30"}`}><div className="flex items-center justify-between"><p className="text-sm font-bold text-zinc-500">{number}</p><div className={`rounded-full px-3 py-1 text-xs font-bold ${complete ? "bg-green-500/20 text-green-300" : "bg-zinc-500/20 text-zinc-400"}`}>{complete ? "Complete" : "Pending"}</div></div><h3 className="mt-4 text-xl font-bold">{title}</h3><p className="mt-2 text-sm text-zinc-400">{description}</p></div>;
}

function NarrativeCard({ title, body }: { title: string; body: string }) {
  return <div className="rounded-3xl border border-white/10 bg-black/30 p-5"><h3 className="text-xl font-bold text-white">{title}</h3><p className="mt-3 text-sm leading-6 text-zinc-400">{body}</p></div>;
}

function SetupCard({ title, body }: { title: string; body: string }) {
  return <div className="rounded-3xl border border-amber-400/10 bg-black/30 p-5"><h3 className="text-lg font-bold text-white">{title}</h3><p className="mt-3 text-sm leading-6 text-zinc-400">{body}</p></div>;
}

function ActionCard({ title, description, inputValue, onInputChange, placeholder, buttonLabel, buttonClassName, onClick }: { title: string; description: string; inputValue: string; onInputChange: (value: string) => void; placeholder: string; buttonLabel: string; buttonClassName: string; onClick: () => void }) {
  return <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-6"><h3 className="text-2xl font-bold">{title}</h3><p className="mt-2 min-h-[48px] text-sm text-zinc-400">{description}</p><input value={inputValue} onChange={(e) => onInputChange(e.target.value)} placeholder={placeholder} className="mt-5 w-full rounded-2xl border border-white/10 bg-black/30 p-4 outline-none placeholder:text-zinc-600 focus:border-blue-400/70" /><button onClick={onClick} className={`mt-4 w-full rounded-2xl p-4 font-bold transition ${buttonClassName}`}>{buttonLabel}</button></div>;
}

function RegistryLine({ label, value }: { label: string; value: string }) {
  return <div className="rounded-2xl border border-white/10 bg-black/30 p-4"><p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">{label}</p><p className="mt-2 break-all font-mono text-sm text-zinc-200">{value}</p></div>;
}

function ActivityRow({ item, shortHash }: { item: ActivityItem; shortHash: (hash: string) => string }) {
  const badgeStyle = item.type === "Deposit" ? "border-green-500/30 bg-green-500/10 text-green-300" : item.type === "Withdraw" ? "border-red-500/30 bg-red-500/10 text-red-300" : item.type === "Borrow" ? "border-blue-500/30 bg-blue-500/10 text-blue-300" : item.type === "Repay" ? "border-yellow-500/30 bg-yellow-500/10 text-yellow-300" : item.type === "Liquidation" ? "border-rose-500/30 bg-rose-500/10 text-rose-300" : "border-purple-500/30 bg-purple-500/10 text-purple-300";
  return <div className="flex flex-col justify-between gap-4 rounded-2xl border border-white/10 bg-black/30 p-5 lg:flex-row lg:items-center"><div className="flex items-start gap-4"><div className={`rounded-full border px-3 py-1 text-xs font-bold ${badgeStyle}`}>{item.type}</div><div><p className="font-semibold text-white">{item.title}</p><p className="mt-1 text-sm text-zinc-400">{item.description}</p></div></div><div className="text-sm text-zinc-500"><p>Block #{item.blockNumber}</p><p className="font-mono">{shortHash(item.txHash)}</p></div></div>;
}
