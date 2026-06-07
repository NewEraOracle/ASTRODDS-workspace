"use client";



import { FaithCertificateControlRoom } from '../components/FaithCertificateControlRoom';
import { FaithEconomicControlRoom } from '../components/FaithEconomicControlRoom';
import { useEffect, useMemo, useState } from "react";
import { ethers } from "ethers";
import { calculatePCSRisk, simulatePCSStress } from "@/lib/pcs";

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


async function safeQueryFilter(contract: any, eventFilter: any, fromBlock?: any, toBlock?: any) {
  try {
    if (!contract || !eventFilter) return [];
    return await contract.queryFilter(eventFilter, fromBlock, toBlock);
  } catch (error) {
    console.warn("FAITH dashboard activity filter skipped:", error);
    return [];
  }
}

export default function Home() {
  const [wallet, setWallet] = useState("");
  const [walletProvider, setWalletProvider] = useState<any>(null);
  const [faithBalance, setFaithBalance] = useState("0");
  const [fusdBalance, seFUSDBalance] = useState("0");
  const [collateral, setCollateral] = useState("0");
  const [debt, setDebt] = useState("0");
  const [vaultActive, setVaultActive] = useState(false);
  const [healthFactor, setHealthFactor] = useState("âˆž");
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

  const healthNumber = healthFactor === "âˆž" ? Number.POSITIVE_INFINITY : Number(healthFactor);

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
    async function autoReconnectWallet() {
      try {
        const activeProvider = window.ethereum;
        if (!activeProvider?.request || wallet) return;

        const accounts = await activeProvider.request({
          method: "eth_accounts",
        });

        if (!accounts?.[0]) return;

        setWalletProvider(activeProvider);
        setWallet(accounts[0]);
        setStatus("Wallet auto-connected - ready");

        await refreshEverything(accounts[0], activeProvider);
      } catch (error) {
        console.warn("Auto reconnect failed:", error);
      }
    }

    autoReconnectWallet();
  }, []);
  useEffect(() => {
    if (wallet) refreshEverything(wallet);
  }, [wallet, walletProvider]);

  const riskStatus = useMemo(() => {
    if (healthFactor === "âˆž") {
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
  const pcsRisk = useMemo(() => {
    return calculatePCSRisk({
      oraclePrice: Number(oraclePrice),
      healthFactor: healthFactor === "âˆž" ? null : Number(healthFactor),
      protocolCollateral: Number(protocolCollateral),
      protocolDebtSupply: Number(protocolDebtSupply),
      vaultActive,
    });
  }, [healthFactor, oraclePrice, protocolCollateral, protocolDebtSupply, vaultActive]);

  const pcsStressScenarios = useMemo(() => {
    return simulatePCSStress({
      oraclePrice: Number(oraclePrice),
      healthFactor: healthFactor === "âˆž" ? null : Number(healthFactor),
      protocolCollateral: Number(protocolCollateral),
      protocolDebtSupply: Number(protocolDebtSupply),
      vaultActive,
    });
  }, [healthFactor, oraclePrice, protocolCollateral, protocolDebtSupply, vaultActive]);


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
      title: "Borrow 5 FUSD",
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
    if (!demoProgress.borrow) return "Next: Borrow 5 FUSD.";
    if (!demoProgress.crash) return "Next: Crash tFAITH price to $0.40.";
    if (!demoProgress.liquidation) return "Next: Liquidate the unsafe tVault.";
    return "Demo completed successfully âœ”";
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
        totalFUSDSupply,
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
      const formattedProtocolDebt = ethers.formatEther(totalFUSDSupply);
      const available = Number(formattedBorrowLimit) - Number(formattedDebt);

      setFaithBalance(formattedFaithBalance);
      seFUSDBalance(formattedFusdBalance);
      setCollateral(formattedCollateral);
      setDebt(formattedDebt);
      setVaultActive(vaultData.active);
      setBorrowLimit(Number(formattedBorrowLimit).toFixed(2));
      setAvailableBorrow(Math.max(available, 0).toFixed(2));
      setOraclePrice(formattedOraclePrice);
      setProtocolCollateral(formattedProtocolCollateral);
      setProtocolDebtSupply(formattedProtocolDebt);
      setHealthFactor(healthRaw === ethers.MaxUint256 ? "âˆž" : (Number(healthRaw) / 100).toFixed(2));
    } catch (error) {
      console.error(error);
      setStatus("Loading protocol data failed âŒ");
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
        safeQueryFilter(vault, vault.filters.CollateralDeposited(), DEPLOYMENT_BLOCK, "latest"),
        safeQueryFilter(vault, vault.filters.CollateralWithdrawn(), DEPLOYMENT_BLOCK, "latest"),
        safeQueryFilter(vault, (typeof vault.filters?.FUSDBorrowed === 'function' ? vault.filters.FUSDBorrowed() : typeof vault.filters?.Borrowed === 'function' ? vault.filters.Borrowed() : typeof vault.filters?.CreditBorrowed === 'function' ? vault.filters.CreditBorrowed() : undefined), DEPLOYMENT_BLOCK, "latest"),
        safeQueryFilter(vault, (typeof vault.filters?.FUSDRepaid === 'function' ? vault.filters.FUSDRepaid() : typeof vault.filters?.Repaid === 'function' ? vault.filters.Repaid() : typeof vault.filters?.CreditRepaid === 'function' ? vault.filters.CreditRepaid() : undefined), DEPLOYMENT_BLOCK, "latest"),
        safeQueryFilter(vault, vault.filters.VaultLiquidated(), DEPLOYMENT_BLOCK, "latest"),
        safeQueryFilter(oracle, oracle.filters.PriceUpdated(), DEPLOYMENT_BLOCK, "latest"),
      ]);

      const items: ActivityItem[] = [];

      for (const event of depositEvents as any[]) {
        const user = event.args.user;
        const amount = Number(ethers.formatEther(event.args.amount));
        items.push({ id: `${event.transactionHash}-${event.index}`, type: "Deposit", title: "Collateral Deposited", description: `${shortAddress(user)} added ${amount} tFAITH collateral to the credit system`, blockNumber: event.blockNumber, txHash: event.transactionHash, user, amount });
      }
      for (const event of withdrawEvents as any[]) {
        const user = event.args.user;
        const amount = Number(ethers.formatEther(event.args.amount));
        items.push({ id: `${event.transactionHash}-${event.index}`, type: "Withdraw", title: "Collateral Withdrawn", description: `${shortAddress(user)} withdrew ${amount} tFAITH collateral from the vault system`, blockNumber: event.blockNumber, txHash: event.transactionHash, user, amount });
      }
      for (const event of borrowEvents as any[]) {
        const user = event.args.user;
        const amount = Number(ethers.formatEther(event.args.amount));
        items.push({ id: `${event.transactionHash}-${event.index}`, type: "Borrow", title: "Stable Credit Borrowed", description: `${shortAddress(user)} minted ${amount} FUSD against collateral`, blockNumber: event.blockNumber, txHash: event.transactionHash, user, amount });
      }
      for (const event of repayEvents as any[]) {
        const user = event.args.user;
        const amount = Number(ethers.formatEther(event.args.amount));
        items.push({ id: `${event.transactionHash}-${event.index}`, type: "Repay", title: "Debt Repaid", description: `${shortAddress(user)} repaid ${amount} FUSD and reduced system debt`, blockNumber: event.blockNumber, txHash: event.transactionHash, user, amount });
      }
      for (const event of liquidationEvents as any[]) {
        const user = event.args.user;
        const liquidator = event.args.liquidator;
        const debtRepaid = Number(ethers.formatEther(event.args.debtRepaid));
        const collateralSeized = Number(ethers.formatEther(event.args.collateralSeized));
        items.push({ id: `${event.transactionHash}-${event.index}`, type: "Liquidation", title: "Liquidation Executed", description: `${shortAddress(liquidator)} cleared unsafe debt for ${shortAddress(user)} â€” ${debtRepaid} FUSD repaid, ${collateralSeized} tFAITH collateral seized`, blockNumber: event.blockNumber, txHash: event.transactionHash, user, liquidator, debtRepaid, collateralSeized });
      }
      for (const event of oracleEvents as any[]) {
        const previousPrice = Number(ethers.formatEther(event.args.previousPrice));
        const newOraclePrice = Number(ethers.formatEther(event.args.newPrice));
        items.push({ id: `${event.transactionHash}-${event.index}`, type: "Oracle", title: "Oracle Shock Recorded", description: `tFAITH oracle moved from $${previousPrice} to $${newOraclePrice}; PCS risk conditions should update from this signal`, blockNumber: event.blockNumber, txHash: event.transactionHash, previousPrice, newPrice: newOraclePrice });
      }

      items.sort((a, b) => b.blockNumber - a.blockNumber);
      setActivity(items.slice(0, 50));
    } catch (error) {
      console.error(error);
      setStatus("Loading on-chain activity failed âŒ");
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

      const accounts = await activeProvider.request({
        method: "eth_requestAccounts",
      });

      if (!accounts?.[0]) {
        throw new Error("No wallet account returned");
      }

      setStatus("Switching to MegaETH Testnet...");

      try {
        await switchToMegaETH(activeProvider);
      } catch (switchError) {
        console.warn("Network switch failed:", switchError);
      }

      const provider = new ethers.BrowserProvider(activeProvider);
      const network = await provider.getNetwork();

      setWallet(accounts[0]);

      if (Number(network.chainId) !== MEGAETH_CHAIN_ID_DECIMAL) {
        setStatus("Wallet connected, but please switch manually to MegaETH Testnet.");
        return;
      }

      setStatus("Wallet connected on MegaETH - ready");
      await refreshEverything(accounts[0], activeProvider);
    } catch (error) {
      console.error(error);
      setStatus("Wallet connection failed. Open in MetaMask browser or use desktop MetaMask.");
    }
  }

  async function resetDemoFlow() {
    setDemoProgress(DEFAULT_DEMO_PROGRESS);
    window.localStorage.setItem(DEMO_PROGRESS_STORAGE_KEY, JSON.stringify(DEFAULT_DEMO_PROGRESS));
    setStatus("Demo Flow reset to 0/5 âœ”");
  }

  async function claimTestFaith() {
    try {
      if (!wallet) return;

      setStatus("Checking tFAITH balance...");

      const provider = await ensureMegaETHProvider();
      const signer = await provider.getSigner();

      const faith = new ethers.Contract(FAITH_TOKEN_ADDRESS, FAITH_TOKEN_ABI, provider);
      const currentBalance = await faith.balanceOf(wallet);

      if (currentBalance > BigInt(0)) {
        updateDemoProgress({ claim: true });
        setStatus("Wallet already has tFAITH - continue demo");
        await refreshEverything(wallet);
        return;
      }

      setStatus("Claiming 1000 tFAITH from faucet...");

      const faucet = new ethers.Contract(FAUCET_ADDRESS, FAUCET_ABI, signer);
      const tx = await faucet.claim();
      await tx.wait();

      updateDemoProgress({ claim: true });
      setStatus("1000 tFAITH claimed successfully");
      await refreshEverything(wallet);
    } catch (error: any) {
      console.error(error);

      try {
        const provider = await ensureMegaETHProvider();
        const faith = new ethers.Contract(FAITH_TOKEN_ADDRESS, FAITH_TOKEN_ABI, provider);
        const currentBalance = await faith.balanceOf(wallet);

        if (currentBalance > BigInt(0)) {
          updateDemoProgress({ claim: true });
          setStatus("Claim already completed - wallet has tFAITH");
          await refreshEverything(wallet);
          return;
        }
      } catch (balanceError) {
        console.error("Balance check after failed claim also failed:", balanceError);
      }

      setStatus("Faucet claim failed. This wallet may have already claimed or the faucet is restricted.");
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
      setStatus("tFAITH deposit successful âœ”");
      setDepositAmount("");
      await refreshEverything(wallet);
    } catch (error) {
      console.error(error);
      setStatus("tFAITH deposit failed âŒ");
    }
  }

  async function borrowFUSD() {
    try {
      if (!borrowAmount || !wallet) return;
      setStatus("Borrowing FUSD...");
      const provider = await ensureMegaETHProvider();
      const signer = await provider.getSigner();
      const vault = new ethers.Contract(VAULT_MANAGER_ADDRESS, VAULT_MANAGER_ABI, signer);
      const tx = await vault.borrow(ethers.parseEther(borrowAmount));
      await tx.wait();
      updateDemoProgress({ borrow: true });
      setStatus("FUSD borrow successful âœ”");
      setBorrowAmount("");
      await refreshEverything(wallet);
    } catch (error) {
      console.error(error);
      setStatus("FUSD borrow failed âŒ");
    }
  }

  async function repayFUSD() {
    try {
      if (!repayAmount || !wallet) return;
      setStatus("Approving FUSD...");
      const provider = await ensureMegaETHProvider();
      const signer = await provider.getSigner();
      const fusd = new ethers.Contract(FUSD_ADDRESS, FUSD_ABI, signer);
      const vault = new ethers.Contract(VAULT_MANAGER_ADDRESS, VAULT_MANAGER_ABI, signer);
      const amount = ethers.parseEther(repayAmount);
      const approveTx = await fusd.approve(VAULT_MANAGER_ADDRESS, amount);
      await approveTx.wait();
      setStatus("Repaying FUSD...");
      const tx = await vault.repay(amount);
      await tx.wait();
      setStatus("FUSD repayment successful âœ”");
      setRepayAmount("");
      await refreshEverything(wallet);
    } catch (error) {
      console.error(error);
      setStatus("FUSD repayment failed âŒ");
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
      setStatus("tFAITH withdrawal successful âœ”");
      setWithdrawAmount("");
      await refreshEverything(wallet);
    } catch (error) {
      console.error(error);
      setStatus("tFAITH withdrawal failed âŒ");
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
        setStatus("Target tVault has no FUSD debt âŒ");
        return;
      }
      setStatus("Approving FUSD for liquidation...");
      const approveTx = await fusd.approve(VAULT_MANAGER_ADDRESS, targetDebt);
      await approveTx.wait();
      setStatus("Liquidating unsafe tVault...");
      const tx = await vault.liquidate(liquidateAddress);
      await tx.wait();
      updateDemoProgress({ liquidation: true });
      setStatus("tVault liquidation successful âœ”");
      setLiquidateAddress("");
      await refreshEverything(wallet);
    } catch (error) {
      console.error(error);
      setStatus("tVault liquidation failed âŒ");
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
      setStatus("tMockOracle price updated âœ”");
      setNewPrice("");
      await refreshEverything(wallet);
    } catch (error) {
      console.error(error);
      setStatus("tMockOracle update failed âŒ");
    }
  }

  return (
    <main className="faith-dashboard min-h-screen p-6 text-white lg:p-8">
      <section className="mb-8 flex flex-col justify-between gap-6 rounded-3xl border border-white/10 bg-white/[0.03] p-8 lg:flex-row lg:items-center">
        <div>
          <div className="mb-3 inline-flex rounded-full border border-blue-500/30 bg-blue-500/10 px-3 py-1 text-sm font-semibold text-blue-300">
            MegaETH-Native Institutional Credit Infrastructure
          </div>
          <h1 className="text-5xl font-bold tracking-tight">FAITH Protocol</h1>
          <p className="mt-3 max-w-2xl text-lg text-zinc-400">
            FAITH Protocol is building MegaETH-native credit, treasury, and risk infrastructure for an autonomous digital economy. Built around vaults, stable credit, PCS monitoring, oracle shock simulation, treasury health, and future capital routing.
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
          Testers need a small amount of MegaETH testnet ETH to pay gas before claiming tFAITH or using the protocol. For mobile testing, the most reliable option is currently the MetaMask mobile browser. Safari and Chrome mobile may not connect consistently during the MVP testnet phase.
        </p>
        <div className="mt-5 grid gap-4 md:grid-cols-3">
          <SetupCard title="1. Open wallet" body="Best mobile option: use the MetaMask mobile browser. Safari/Chrome mobile may not connect consistently during MVP testing." />
          <div className="rounded-3xl border border-white/10 bg-black/30 p-5">
            <h3 className="text-2xl font-bold">2. Get gas</h3>
            <p className="mt-5 text-zinc-300">
              Get MegaETH testnet ETH for gas from the official MegaETH testnet faucet.
            </p>
            <a
              href="https://testnet.megaeth.com"
              target="_blank"
              rel="noreferrer"
              className="mt-5 inline-flex rounded-full border border-cyan-300/30 bg-cyan-300/10 px-5 py-3 text-sm font-bold text-cyan-100 transition hover:bg-cyan-300/20"
            >
              Open MegaETH Faucet
            </a>
          </div>
          <SetupCard title="3. Run demo" body="Claim 1000 tFAITH, deposit, borrow, crash the oracle, and liquidate." />
        </div>
      </section>

      <section className="mb-8 rounded-3xl border border-cyan-500/20 bg-cyan-500/[0.06] p-6">
        <div className="mb-6 flex flex-col justify-between gap-4 lg:flex-row lg:items-center">
          <div>
            <div className="mb-2 inline-flex rounded-full border border-cyan-400/30 bg-cyan-400/10 px-3 py-1 text-sm font-bold text-cyan-200">
              Investor Demo Flow
            </div>
            <h2 className="text-3xl font-bold">Demo Flow: Prove the FAITH Protocol Risk Loop</h2>
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
          <p className="text-sm font-semibold uppercase tracking-wide text-zinc-500">Recommended Demo Action</p>
          <p className="mt-2 text-lg font-semibold text-white">{recommendedAction}</p>
          <p className="mt-2 text-sm text-zinc-500">This guided demo shows the full credit and risk cycle: connect wallet, claim test collateral, deposit, borrow, simulate an oracle shock, monitor liquidation risk, and reset the presentation tracker. Reset does not change your wallet, balances, or protocol state.</p>
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
        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-6">
          <div className="rounded-3xl border border-cyan-400/20 bg-cyan-400/10 p-5 shadow-[0_0_45px_rgba(34,211,238,0.08)]">
            <p className="text-xs font-black uppercase tracking-[0.25em] text-cyan-200">PCS Status</p>
            <h3 className="mt-3 text-2xl font-black text-white">
              {pcsRisk.pcsRiskLevel}
            </h3>
            <p className="mt-2 text-xs text-zinc-400">Parameter Control System monitor</p>

            <div className="mt-5 space-y-2 text-xs">
              <div className="flex justify-between gap-3">
                <span className="text-zinc-500">System Risk</span>
                <span className="text-cyan-100">{pcsRisk.pcsRiskLevel} Â· {pcsRisk.pcsRiskScore}/100</span>
              </div>
              <div className="flex justify-between gap-3">
                <span className="text-zinc-500">Oracle Risk</span>
                <span className={pcsRisk.oracleRisk === "Critical" || pcsRisk.oracleRisk === "High" ? "text-red-300" : pcsRisk.oracleRisk === "Elevated" ? "text-orange-300" : "text-emerald-300"}>
                  {pcsRisk.oracleRisk}
                </span>
              </div>
              <div className="flex justify-between gap-3">
                <span className="text-zinc-500">Treasury</span>
                <span className="text-emerald-300">{Number(protocolCollateral) > 0 ? "Active" : "Standby"}</span>
              </div>
              <div className="flex justify-between gap-3">
                <span className="text-zinc-500">PCS Action</span>
                <span className="text-cyan-100">
                  {pcsRisk.suggestedParameterResponse}
                </span>
              </div>
            </div>
          </div>

          <div className="rounded-3xl border border-emerald-400/20 bg-emerald-400/10 p-5 shadow-[0_0_45px_rgba(16,185,129,0.08)]">
            <p className="text-xs font-black uppercase tracking-[0.25em] text-emerald-200">Treasury Health</p>
            <h3 className={`mt-3 text-2xl font-black ${
              pcsRisk.treasuryCoverage === "Weak"
                ? "text-red-300"
                : pcsRisk.treasuryCoverage === "Moderate"
                  ? "text-orange-300"
                  : "text-emerald-300"
            }`}>
              {pcsRisk.treasuryCoverage}
            </h3>
            <p className="mt-2 text-xs text-zinc-400">PCS reserve coverage and risk buffer monitor</p>

            <div className="mt-5 space-y-2 text-xs">
              <div className="flex justify-between gap-3">
                <span className="text-zinc-500">Reserve Status</span>
                <span className={Number(protocolCollateral) > 0 ? "text-emerald-300" : "text-zinc-400"}>
                  {Number(protocolCollateral) > 0 ? "Active" : "Empty"}
                </span>
              </div>
              <div className="flex justify-between gap-3">
                <span className="text-zinc-500">Collateral</span>
                <span className="text-white">{Number(protocolCollateral).toLocaleString()} tFAITH</span>
              </div>
              <div className="flex justify-between gap-3">
                <span className="text-zinc-500">Debt Coverage</span>
                <span className="text-cyan-100">
                  {pcsRisk.debtCoverageRatio === null ? "No Debt" : `${pcsRisk.debtCoverageRatio.toFixed(2)}x`}
                </span>
              </div>
              <div className="flex justify-between gap-3">
                <span className="text-zinc-500">Reserve Target</span>
                <span className="text-blue-100">{pcsRisk.treasuryReserveTarget}%</span>
              </div>
              <div className="flex justify-between gap-3">
                <span className="text-zinc-500">Treasury Action</span>
                <span className={pcsRisk.treasuryCoverage === "Weak" || pcsRisk.treasuryCoverage === "Moderate" ? "text-orange-300" : "text-emerald-300"}>
                  {pcsRisk.treasuryCoverage === "Weak"
                    ? "Increase reserves"
                    : pcsRisk.treasuryCoverage === "Moderate"
                      ? "Monitor reserves"
                      : "Maintain reserves"}
                </span>
              </div>
            </div>
          </div>

          <MetricCard label="Total tFAITH Collateral" value={Number(protocolCollateral).toLocaleString()} helper="Held inside tVaultManager" />
          <MetricCard label="Total FUSD Debt Supply" value={Number(protocolDebtSupply).toLocaleString()} helper="Outstanding test credit" />
          <MetricCard label="tFAITH Oracle Price" value={`$${oraclePrice}`} helper="tMockOracle live value" />
          <MetricCard label="tVault Address" value={`${VAULT_MANAGER_ADDRESS.slice(0, 6)}...${VAULT_MANAGER_ADDRESS.slice(-4)}`} helper="Current test deployment" />
        </div>
      </section>

      <section className="mb-8 rounded-3xl border border-cyan-400/20 bg-cyan-400/[0.06] p-6 shadow-[0_0_60px_rgba(34,211,238,0.08)]">
        <div className="mb-6 flex flex-col justify-between gap-4 lg:flex-row lg:items-center">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.28em] text-cyan-200">PCS Risk Module</p>
            <h2 className="mt-2 text-2xl font-bold">PCS Parameter Engine</h2>
            <p className="mt-2 max-w-4xl text-zinc-400">
              Rule-based protocol risk module for the MVP. PCS reads testnet protocol conditions and suggests
              protocol-level parameter responses. It does not provide financial advice, investment advice, or user trading recommendations.
            </p>
          </div>
          <div className={`rounded-full border px-4 py-2 text-sm font-bold ${riskStatus.bg} ${riskStatus.border} ${riskStatus.color}`}>
            System Risk: {pcsRisk.pcsRiskLevel} Â· {pcsRisk.pcsRiskScore}/100
          </div>
        </div>

        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-3xl border border-white/10 bg-black/30 p-5">
            <p className="text-xs font-black uppercase tracking-[0.20em] text-zinc-400">Oracle Risk</p>
            <h3 className={`mt-3 text-2xl font-black ${pcsRisk.oracleRisk === "Critical" || pcsRisk.oracleRisk === "High" ? "text-red-300" : pcsRisk.oracleRisk === "Elevated" ? "text-orange-300" : "text-emerald-300"}`}>
              {pcsRisk.oracleRisk}
            </h3>
            <p className="mt-2 text-sm text-zinc-500">Oracle price shock sensitivity.</p>
          </div>

          <div className="rounded-3xl border border-white/10 bg-black/30 p-5">
            <p className="text-xs font-black uppercase tracking-[0.20em] text-zinc-400">Treasury Coverage</p>
            <h3 className={`mt-3 text-2xl font-black ${pcsRisk.treasuryCoverage === "Weak" ? "text-red-300" : pcsRisk.treasuryCoverage === "Moderate" ? "text-orange-300" : "text-emerald-300"}`}>
              {pcsRisk.treasuryCoverage}
            </h3>
            <p className="mt-2 text-sm text-zinc-500">Reserve visibility for credit risk protection.</p>
          </div>

          <div className="rounded-3xl border border-white/10 bg-black/30 p-5">
            <p className="text-xs font-black uppercase tracking-[0.20em] text-zinc-400">Liquidation Pressure</p>
            <h3 className={`mt-3 text-2xl font-black ${pcsRisk.liquidationPressure === "Critical" || pcsRisk.liquidationPressure === "High" ? "text-red-300" : pcsRisk.liquidationPressure === "Rising" ? "text-orange-300" : "text-emerald-300"}`}>
              {pcsRisk.liquidationPressure}
            </h3>
            <p className="mt-2 text-sm text-zinc-500">Vault safety pressure from debt and collateral changes.</p>
          </div>

          <div className="rounded-3xl border border-white/10 bg-black/30 p-5">
            <p className="text-xs font-black uppercase tracking-[0.20em] text-zinc-400">Suggested Parameter Response</p>
            <h3 className="mt-3 text-xl font-black text-cyan-100">
              {pcsRisk.suggestedParameterResponse}
            </h3>
            <p className="mt-2 text-sm text-zinc-500">Protocol-level response for the current testnet state.</p>
          </div>
        </div>

        <div className="mt-6 rounded-2xl border border-cyan-300/20 bg-black/30 p-5">
          <p className="text-xs font-black uppercase tracking-[0.22em] text-cyan-200">Risk Rationale</p>
          <p className="mt-3 text-sm leading-7 text-zinc-300">
            {pcsRisk.riskRationale}
          </p>
        </div>
      </section>

      <section className="mb-8 rounded-3xl border border-cyan-400/20 bg-cyan-400/[0.05] p-6 shadow-[0_0_60px_rgba(34,211,238,0.08)]">
        <div className="mb-6 flex flex-col justify-between gap-4 lg:flex-row lg:items-center">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.28em] text-cyan-200">PCS Risk Radar</p>
            <h2 className="mt-2 text-2xl font-bold">Protocol Risk Breakdown</h2>
            <p className="mt-2 max-w-4xl text-zinc-400">
              PCS decomposes system risk into oracle, vault, liquidation, utilization, treasury, and system-level conditions.
            </p>
          </div>
          <div className={`rounded-full border px-4 py-2 text-sm font-bold ${
            pcsRisk.pcsRiskLevel === "Critical" || pcsRisk.pcsRiskLevel === "High Risk"
              ? "border-red-400/30 bg-red-400/10 text-red-200"
              : pcsRisk.pcsRiskLevel === "Warning"
                ? "border-orange-400/30 bg-orange-400/10 text-orange-200"
                : "border-emerald-400/30 bg-emerald-400/10 text-emerald-200"
          }`}>
            System Risk: {pcsRisk.pcsRiskLevel} Â· {pcsRisk.pcsRiskScore}/100
          </div>
        </div>

        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
          <div className="rounded-3xl border border-white/10 bg-black/30 p-5">
            <p className="text-xs font-black uppercase tracking-[0.20em] text-zinc-400">Oracle Risk</p>
            <h3 className={`mt-3 text-2xl font-black ${pcsRisk.oracleRisk === "Critical" || pcsRisk.oracleRisk === "High" ? "text-red-300" : pcsRisk.oracleRisk === "Elevated" ? "text-orange-300" : "text-emerald-300"}`}>
              {pcsRisk.oracleRisk}
            </h3>
            <p className="mt-2 text-sm text-zinc-500">Collateral price signal from tMockOracle.</p>
          </div>

          <div className="rounded-3xl border border-white/10 bg-black/30 p-5">
            <p className="text-xs font-black uppercase tracking-[0.20em] text-zinc-400">Vault Health Risk</p>
            <h3 className={`mt-3 text-2xl font-black ${pcsRisk.vaultHealthRisk === "Critical" || pcsRisk.vaultHealthRisk === "High" ? "text-red-300" : pcsRisk.vaultHealthRisk === "Moderate" ? "text-orange-300" : "text-emerald-300"}`}>
              {pcsRisk.vaultHealthRisk}
            </h3>
            <p className="mt-2 text-sm text-zinc-500">Risk level from current vault health factor.</p>
          </div>

          <div className="rounded-3xl border border-white/10 bg-black/30 p-5">
            <p className="text-xs font-black uppercase tracking-[0.20em] text-zinc-400">Liquidation Pressure</p>
            <h3 className={`mt-3 text-2xl font-black ${pcsRisk.liquidationPressure === "Critical" || pcsRisk.liquidationPressure === "High" ? "text-red-300" : pcsRisk.liquidationPressure === "Rising" ? "text-orange-300" : "text-emerald-300"}`}>
              {pcsRisk.liquidationPressure}
            </h3>
            <p className="mt-2 text-sm text-zinc-500">Pressure created by collateral and debt conditions.</p>
          </div>

          <div className="rounded-3xl border border-white/10 bg-black/30 p-5">
            <p className="text-xs font-black uppercase tracking-[0.20em] text-zinc-400">Borrow Utilization</p>
            <h3 className="mt-3 text-2xl font-black text-white">
              {(pcsRisk.borrowUtilization * 100).toFixed(2)}%
            </h3>
            <p className="mt-2 text-sm text-zinc-500">Debt supply relative to protocol collateral.</p>
          </div>

          <div className="rounded-3xl border border-white/10 bg-black/30 p-5">
            <p className="text-xs font-black uppercase tracking-[0.20em] text-zinc-400">Treasury Coverage</p>
            <h3 className={`mt-3 text-2xl font-black ${pcsRisk.treasuryCoverage === "Weak" ? "text-red-300" : pcsRisk.treasuryCoverage === "Moderate" ? "text-orange-300" : "text-emerald-300"}`}>
              {pcsRisk.treasuryCoverage}
            </h3>
            <p className="mt-2 text-sm text-zinc-500">Collateral coverage against outstanding test credit.</p>
          </div>

          <div className="rounded-3xl border border-white/10 bg-black/30 p-5">
            <p className="text-xs font-black uppercase tracking-[0.20em] text-zinc-400">System Risk</p>
            <h3 className={`mt-3 text-2xl font-black ${pcsRisk.pcsRiskLevel === "Critical" || pcsRisk.pcsRiskLevel === "High Risk" ? "text-red-300" : pcsRisk.pcsRiskLevel === "Warning" ? "text-orange-300" : "text-emerald-300"}`}>
              {pcsRisk.pcsRiskScore}/100
            </h3>
            <p className="mt-2 text-sm text-zinc-500">{pcsRisk.pcsRiskLevel} protocol risk state.</p>
          </div>
        </div>
      </section>

      <section className="mb-8 rounded-3xl border border-amber-400/20 bg-amber-400/[0.06] p-6 shadow-[0_0_60px_rgba(245,158,11,0.08)]">
        <div className="mb-6 flex flex-col justify-between gap-4 lg:flex-row lg:items-center">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.28em] text-amber-200">PCS Action Queue</p>
            <h2 className="mt-2 text-2xl font-bold">Prioritized Protocol Responses</h2>
            <p className="mt-2 max-w-4xl text-zinc-400">
              PCS converts risk signals into a prioritized protocol-level action queue. These are testnet control recommendations, not user financial advice.
            </p>
          </div>
          <div className="rounded-full border border-amber-300/30 bg-amber-300/10 px-4 py-2 text-sm font-bold text-amber-100">
            {pcsRisk.actionQueue.length} Active Signals
          </div>
        </div>

        <div className="grid gap-5 lg:grid-cols-3">
          {pcsRisk.actionQueue.map((action, index) => (
            <div key={action.id} className="rounded-3xl border border-white/10 bg-black/30 p-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-black uppercase tracking-[0.20em] text-zinc-400">
                    Action {index + 1}
                  </p>
                  <h3 className="mt-3 text-xl font-black text-white">{action.title}</h3>
                </div>
                <span className={`rounded-full border px-3 py-1 text-xs font-bold ${
                  action.priority === "Critical"
                    ? "border-red-400/30 bg-red-400/10 text-red-200"
                    : action.priority === "High"
                      ? "border-orange-400/30 bg-orange-400/10 text-orange-200"
                      : action.priority === "Medium"
                        ? "border-amber-400/30 bg-amber-400/10 text-amber-200"
                        : "border-emerald-400/30 bg-emerald-400/10 text-emerald-200"
                }`}>
                  {action.priority}
                </span>
              </div>
              <p className="mt-4 text-sm leading-6 text-zinc-400">{action.reason}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mb-8 rounded-3xl border border-blue-400/20 bg-blue-400/[0.06] p-6 shadow-[0_0_60px_rgba(59,130,246,0.08)]">
        <div className="mb-6 flex flex-col justify-between gap-4 lg:flex-row lg:items-center">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.28em] text-blue-200">PCS Control Layer</p>
            <h2 className="mt-2 text-2xl font-bold">PCS Risk Parameter Panel</h2>
            <p className="mt-2 max-w-4xl text-zinc-400">
              PCS translates protocol risk into suggested parameter responses for the current testnet state.
              These are protocol-level controls, not user financial advice.
            </p>
          </div>
          <div className={`rounded-full border px-4 py-2 text-sm font-bold ${pcsRisk.emergencyMode ? "border-red-400/30 bg-red-400/10 text-red-200" : "border-emerald-400/30 bg-emerald-400/10 text-emerald-200"}`}>
            Emergency Mode: {pcsRisk.emergencyMode ? "Recommended" : "Off"}
          </div>
        </div>

        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-3xl border border-white/10 bg-black/30 p-5">
            <p className="text-xs font-black uppercase tracking-[0.20em] text-zinc-400">Current LTV</p>
            <h3 className="mt-3 text-2xl font-black text-white">{pcsRisk.currentLTV}%</h3>
            <p className="mt-2 text-sm text-zinc-500">Current testnet borrow parameter.</p>
          </div>

          <div className="rounded-3xl border border-white/10 bg-black/30 p-5">
            <p className="text-xs font-black uppercase tracking-[0.20em] text-zinc-400">Suggested LTV</p>
            <h3 className={`mt-3 text-2xl font-black ${pcsRisk.suggestedLTV < pcsRisk.currentLTV ? "text-orange-300" : "text-emerald-300"}`}>
              {pcsRisk.suggestedLTV}%
            </h3>
            <p className="mt-2 text-sm text-zinc-500">PCS suggested protocol-level LTV response.</p>
          </div>

          <div className="rounded-3xl border border-white/10 bg-black/30 p-5">
            <p className="text-xs font-black uppercase tracking-[0.20em] text-zinc-400">Liquidation Threshold</p>
            <h3 className="mt-3 text-2xl font-black text-cyan-100">{pcsRisk.liquidationThreshold}%</h3>
            <p className="mt-2 text-sm text-zinc-500">Protocol solvency protection threshold.</p>
          </div>

          <div className="rounded-3xl border border-white/10 bg-black/30 p-5">
            <p className="text-xs font-black uppercase tracking-[0.20em] text-zinc-400">Reserve Target</p>
            <h3 className="mt-3 text-2xl font-black text-blue-100">{pcsRisk.treasuryReserveTarget}%</h3>
            <p className="mt-2 text-sm text-zinc-500">PCS suggested treasury reserve target.</p>
          </div>
        </div>

        <div className="mt-5 grid gap-5 md:grid-cols-2">
          <div className="rounded-3xl border border-white/10 bg-black/30 p-5">
            <p className="text-xs font-black uppercase tracking-[0.20em] text-zinc-400">Borrow Utilization</p>
            <h3 className="mt-3 text-2xl font-black text-white">
              {(pcsRisk.borrowUtilization * 100).toFixed(2)}%
            </h3>
            <p className="mt-2 text-sm text-zinc-500">Debt supply relative to protocol collateral.</p>
          </div>

          <div className="rounded-3xl border border-white/10 bg-black/30 p-5">
            <p className="text-xs font-black uppercase tracking-[0.20em] text-zinc-400">Debt Coverage</p>
            <h3 className="mt-3 text-2xl font-black text-white">
              {pcsRisk.debtCoverageRatio === null ? "No Debt" : `${pcsRisk.debtCoverageRatio.toFixed(2)}x`}
            </h3>
            <p className="mt-2 text-sm text-zinc-500">Collateral coverage against outstanding test credit.</p>
          </div>
        </div>
      </section>

      <section className="mb-8 rounded-3xl border border-fuchsia-400/20 bg-fuchsia-400/[0.06] p-6 shadow-[0_0_60px_rgba(217,70,239,0.08)]">
        <div className="mb-6 flex flex-col justify-between gap-4 lg:flex-row lg:items-center">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.28em] text-fuchsia-200">PCS Stress Timeline</p>
            <h2 className="mt-2 text-2xl font-bold">Risk Progression Timeline</h2>
            <p className="mt-2 max-w-4xl text-zinc-400">
              PCS maps the current protocol state into projected collateral shock stages, showing how risk could evolve before emergency controls become necessary.
            </p>
          </div>
          <div className={`rounded-full border px-4 py-2 text-sm font-bold ${
            pcsRisk.emergencyMode
              ? "border-red-400/30 bg-red-400/10 text-red-200"
              : "border-fuchsia-300/30 bg-fuchsia-300/10 text-fuchsia-100"
          }`}>
            Emergency Trigger: {pcsRisk.emergencyMode ? "Recommended" : "Not Active"}
          </div>
        </div>

        <div className="grid gap-4 lg:grid-cols-4">
          <div className="rounded-3xl border border-white/10 bg-black/30 p-5">
            <p className="text-xs font-black uppercase tracking-[0.20em] text-zinc-400">Current State</p>
            <h3 className={`mt-3 text-2xl font-black ${
              pcsRisk.pcsRiskLevel === "Critical" || pcsRisk.pcsRiskLevel === "High Risk"
                ? "text-red-300"
                : pcsRisk.pcsRiskLevel === "Warning"
                  ? "text-orange-300"
                  : "text-emerald-300"
            }`}>
              {pcsRisk.pcsRiskLevel}
            </h3>
            <div className="mt-4 space-y-2 text-sm">
              <div className="flex justify-between gap-3">
                <span className="text-zinc-500">Risk Score</span>
                <span className="text-cyan-100">{pcsRisk.pcsRiskScore}/100</span>
              </div>
              <div className="flex justify-between gap-3">
                <span className="text-zinc-500">Oracle</span>
                <span className="text-white">${Number(oraclePrice).toFixed(3)}</span>
              </div>
              <div className="flex justify-between gap-3">
                <span className="text-zinc-500">PCS Response</span>
                <span className="text-fuchsia-100">{pcsRisk.suggestedParameterResponse}</span>
              </div>
            </div>
          </div>

          {pcsStressScenarios.map((scenario) => (
            <div key={`timeline-${scenario.dropPercent}`} className="rounded-3xl border border-white/10 bg-black/30 p-5">
              <p className="text-xs font-black uppercase tracking-[0.20em] text-zinc-400">
                -{scenario.dropPercent}% Stage
              </p>
              <h3 className={`mt-3 text-2xl font-black ${
                scenario.projectedRiskLevel === "Critical" || scenario.projectedRiskLevel === "High Risk"
                  ? "text-red-300"
                  : scenario.projectedRiskLevel === "Warning"
                    ? "text-orange-300"
                    : "text-emerald-300"
              }`}>
                {scenario.projectedRiskLevel}
              </h3>
              <div className="mt-4 space-y-2 text-sm">
                <div className="flex justify-between gap-3">
                  <span className="text-zinc-500">Projected Score</span>
                  <span className="text-cyan-100">{scenario.projectedRiskScore}/100</span>
                </div>
                <div className="flex justify-between gap-3">
                  <span className="text-zinc-500">Projected Price</span>
                  <span className="text-white">${scenario.projectedOraclePrice.toFixed(3)}</span>
                </div>
                <div className="flex justify-between gap-3">
                  <span className="text-zinc-500">PCS Response</span>
                  <span className="text-fuchsia-100">{scenario.projectedParameterResponse}</span>
                </div>
              </div>
            </div>
          ))}
        </div>

        <div className="mt-6 rounded-2xl border border-fuchsia-300/20 bg-black/30 p-5">
          <p className="text-xs font-black uppercase tracking-[0.22em] text-fuchsia-200">Timeline Interpretation</p>
          <p className="mt-3 text-sm leading-7 text-zinc-300">
            PCS uses the current risk score and projected shock scenarios to visualize how protocol risk could progress over time. This timeline is a testnet simulation layer for protocol monitoring and does not represent user financial advice.
          </p>
        </div>
      </section>

      <section className="mb-8 rounded-3xl border border-purple-400/20 bg-purple-400/[0.06] p-6 shadow-[0_0_60px_rgba(168,85,247,0.08)]">
        <div className="mb-6 flex flex-col justify-between gap-4 lg:flex-row lg:items-center">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.28em] text-purple-200">PCS Stress Simulator</p>
            <h2 className="mt-2 text-2xl font-bold">Projected Collateral Shock Scenarios</h2>
            <p className="mt-2 max-w-4xl text-zinc-400">
              PCS projects protocol risk under additional collateral price shocks. This is a testnet risk simulation for protocol-level monitoring only.
            </p>
          </div>
          <div className="rounded-full border border-purple-300/30 bg-purple-300/10 px-4 py-2 text-sm font-bold text-purple-100">
            Stress Projection
          </div>
        </div>

        <div className="grid gap-5 md:grid-cols-3">
          {pcsStressScenarios.map((scenario) => (
            <div key={scenario.dropPercent} className="rounded-3xl border border-white/10 bg-black/30 p-5">
              <p className="text-xs font-black uppercase tracking-[0.20em] text-zinc-400">
                -{scenario.dropPercent}% Shock
              </p>
              <h3 className={`mt-3 text-2xl font-black ${
                scenario.projectedRiskLevel === "Critical" || scenario.projectedRiskLevel === "High Risk"
                  ? "text-red-300"
                  : scenario.projectedRiskLevel === "Warning"
                    ? "text-orange-300"
                    : "text-emerald-300"
              }`}>
                {scenario.projectedRiskLevel}
              </h3>
              <div className="mt-4 space-y-2 text-sm">
                <div className="flex justify-between gap-3">
                  <span className="text-zinc-500">Projected Price</span>
                  <span className="text-white">${scenario.projectedOraclePrice.toFixed(3)}</span>
                </div>
                <div className="flex justify-between gap-3">
                  <span className="text-zinc-500">Risk Score</span>
                  <span className="text-cyan-100">{scenario.projectedRiskScore}/100</span>
                </div>
                <div className="flex justify-between gap-3">
                  <span className="text-zinc-500">PCS Response</span>
                  <span className="text-purple-100">{scenario.projectedParameterResponse}</span>
                </div>
              </div>
              <p className="mt-4 text-xs leading-6 text-zinc-400">
                {scenario.projectedRationale}
              </p>
            </div>
          ))}
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
        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
          <MetricCard label="tFAITH Balance" value={Number(faithBalance).toLocaleString()} />
          <MetricCard label="FUSD Balance" value={Number(fusdBalance).toLocaleString()} />
          <MetricCard label="Collateral (FAITH)" value={collateral} />
          <MetricCard label="Debt (fUSD)" value={debt} />
          <MetricCard label="Borrow Limit (fUSD)" value={borrowLimit} />
          <MetricCard label="Available Borrow (fUSD)" value={availableBorrow} />
          <div className="rounded-3xl border border-rose-400/20 bg-rose-400/10 p-5 shadow-[0_0_45px_rgba(244,63,94,0.08)]">
            <p className="text-xs font-black uppercase tracking-[0.22em] text-rose-200">Liquidation Risk</p>
            <h3 className={`mt-3 text-2xl font-black ${riskStatus.label === "Liquidatable" ? "text-red-300" : riskStatus.label === "Warning" ? "text-orange-300" : "text-white"}`}>
              {riskStatus.label === "Liquidatable" ? "Critical" : riskStatus.label === "Warning" ? "Warning" : "Controlled"}
            </h3>
            <p className="mt-2 text-xs text-zinc-400">Vault safety and liquidation monitor</p>

            <div className="mt-5 space-y-2 text-xs">
              <div className="flex justify-between gap-3">
                <span className="text-zinc-500">Current Status</span>
                <span className="text-cyan-100">{pcsRisk.pcsRiskLevel} Â· {pcsRisk.pcsRiskScore}/100</span>
              </div>
              <div className="flex justify-between gap-3">
                <span className="text-zinc-500">Health Factor</span>
                <span className="text-white">{healthFactor}</span>
              </div>
              <div className="flex justify-between gap-3">
                <span className="text-zinc-500">Debt Position</span>
                <span className="text-white">{Number(debt).toLocaleString()} FUSD</span>
              </div>
              <div className="flex justify-between gap-3">
                <span className="text-zinc-500">Collateral at Risk</span>
                <span className={riskStatus.label === "Liquidatable" ? "text-red-300" : riskStatus.label === "Warning" ? "text-orange-300" : "text-emerald-300"}>
                  {riskStatus.label === "No Debt" ? "None" : `${Number(collateral).toLocaleString()} tFAITH`}
                </span>
              </div>
              <div className="flex justify-between gap-3">
                <span className="text-zinc-500">Protocol Response</span>
                <span className="text-cyan-100">
                  {riskStatus.label === "Liquidatable" ? "Allow liquidation" : riskStatus.label === "Warning" ? "Monitor vault" : "No action"}
                </span>
              </div>
            </div>
          </div>

          <div className="rounded-3xl border border-white/10 bg-black/30 p-5">
            <p className="text-sm text-zinc-400">Health Factor</p>
            <p className={`mt-3 break-words text-2xl font-bold ${healthFactor !== "âˆž" && Number(healthFactor) < 1.1 ? "text-red-400" : healthFactor !== "âˆž" && Number(healthFactor) < 1.5 ? "text-orange-300" : "text-green-400"}`}>{healthFactor}</p>
            <div className="mt-4">
              <div className="h-3 w-full overflow-hidden rounded-full bg-white/10">
                <div className={`h-full transition-all duration-700 ${healthFactor !== "âˆž" && Number(healthFactor) < 1.1 ? "bg-red-500" : healthFactor !== "âˆž" && Number(healthFactor) < 1.5 ? "bg-orange-400" : "bg-emerald-400"}`} style={{ width: healthFactor === "âˆž" ? "100%" : `${Math.min(100, Number(healthFactor) * 50)}%` }} />
              </div>
              <div className="mt-2 flex justify-between text-[10px] font-semibold tracking-wide text-zinc-500">
                <span>DANGER</span><span>WARNING</span><span>SAFE</span>
              </div>
            </div>
            <p className="mt-2 text-xs text-zinc-500">Live solvency monitoring powered by PCSMonitor.</p>
          </div>
        </div>
      </section>

      <section className="mb-8 rounded-3xl border border-white/10 bg-white/[0.03] p-6">
        <div className="mb-6">
          <p className="text-xs font-black uppercase tracking-[0.28em] text-cyan-200">Core Thesis</p>
          <h2 className="mt-2 text-2xl font-bold">Human-Built, Machine-Regulated Economy</h2>
          <p className="mt-2 max-w-4xl text-zinc-400">
            FAITH connects human-built productive value to a machine-regulated financial layer on MegaETH.
            Humans build the world. Technology regulates the economy. FAITH connects both layers through credit,
            treasury, PCS monitoring, and future capital routing.
          </p>
        </div>

        <div className="grid gap-5 md:grid-cols-3">
          <div className="rounded-3xl border border-white/10 bg-black/30 p-5">
            <p className="text-xs font-black uppercase tracking-[0.22em] text-zinc-400">Layer 01</p>
            <h3 className="mt-3 text-xl font-black text-white">Human Economy Layer</h3>
            <p className="mt-2 text-sm leading-6 text-zinc-500">
              Real estate, energy, ventures, businesses, infrastructure, technology, and productive assets.
            </p>
            <p className="mt-5 text-xs font-bold uppercase tracking-[0.18em] text-cyan-200">
              Humans build productive value
            </p>
          </div>

          <div className="rounded-3xl border border-cyan-400/20 bg-cyan-400/10 p-5 shadow-[0_0_45px_rgba(34,211,238,0.08)]">
            <p className="text-xs font-black uppercase tracking-[0.22em] text-cyan-200">Layer 02</p>
            <h3 className="mt-3 text-xl font-black text-white">Digital Credit Layer</h3>
            <p className="mt-2 text-sm leading-6 text-zinc-400">
              Vaults, collateral, stable credit, treasury reserves, liquidity, protocol activity, and settlement rails.
            </p>
            <p className="mt-5 text-xs font-bold uppercase tracking-[0.18em] text-cyan-100">
              FAITH transforms value into credit
            </p>
          </div>

          <div className="rounded-3xl border border-emerald-400/20 bg-emerald-400/10 p-5 shadow-[0_0_45px_rgba(16,185,129,0.08)]">
            <p className="text-xs font-black uppercase tracking-[0.22em] text-emerald-200">Layer 03</p>
            <h3 className="mt-3 text-xl font-black text-white">Machine Regulation Layer</h3>
            <p className="mt-2 text-sm leading-6 text-zinc-400">
              PCS, oracle shocks, vault health, liquidation pressure, treasury coverage, and risk monitoring.
            </p>
            <p className="mt-5 text-xs font-bold uppercase tracking-[0.18em] text-emerald-200">
              Technology regulates the credit system
            </p>
          </div>
        </div>
      </section>

      <section className="mb-8 rounded-3xl border border-cyan-400/15 bg-white/[0.03] p-6">
        <div className="mb-6 flex flex-col justify-between gap-4 lg:flex-row lg:items-center">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.28em] text-cyan-200">Research / Future Phase</p>
            <h2 className="mt-2 text-2xl font-bold">Future Capital Routing</h2>
            <p className="mt-2 max-w-3xl text-zinc-400">
              FAITH Protocol may eventually route capital toward productive real-world sectors through compliant,
              audited, partner-driven structures. This module is a roadmap layer, not a live investment product.
            </p>
          </div>
          <div className="rounded-full border border-cyan-400/20 bg-cyan-400/10 px-4 py-2 text-sm font-bold text-cyan-200">
            Compliance Required
          </div>
        </div>

        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-5">
          <div className="rounded-3xl border border-white/10 bg-black/30 p-5">
            <p className="text-xs font-black uppercase tracking-[0.20em] text-zinc-400">Capital Pool</p>
            <h3 className="mt-3 text-xl font-black text-white">Real Estate</h3>
            <p className="mt-2 text-sm text-zinc-500">Future productive asset pool for property-backed infrastructure.</p>
            <p className="mt-5 text-xs font-bold uppercase tracking-[0.18em] text-cyan-200">Research Phase</p>
          </div>

          <div className="rounded-3xl border border-white/10 bg-black/30 p-5">
            <p className="text-xs font-black uppercase tracking-[0.20em] text-zinc-400">Capital Pool</p>
            <h3 className="mt-3 text-xl font-black text-white">Energy</h3>
            <p className="mt-2 text-sm text-zinc-500">Future infrastructure layer for energy and productive systems.</p>
            <p className="mt-5 text-xs font-bold uppercase tracking-[0.18em] text-cyan-200">Partner Required</p>
          </div>

          <div className="rounded-3xl border border-white/10 bg-black/30 p-5">
            <p className="text-xs font-black uppercase tracking-[0.20em] text-zinc-400">Capital Pool</p>
            <h3 className="mt-3 text-xl font-black text-white">Ventures</h3>
            <p className="mt-2 text-sm text-zinc-500">Future capital routing toward builders, businesses, and growth projects.</p>
            <p className="mt-5 text-xs font-bold uppercase tracking-[0.18em] text-cyan-200">Due Diligence</p>
          </div>

          <div className="rounded-3xl border border-white/10 bg-black/30 p-5">
            <p className="text-xs font-black uppercase tracking-[0.20em] text-zinc-400">Capital Pool</p>
            <h3 className="mt-3 text-xl font-black text-white">Technology</h3>
            <p className="mt-2 text-sm text-zinc-500">Future support for AI, compute, software, and technical infrastructure.</p>
            <p className="mt-5 text-xs font-bold uppercase tracking-[0.18em] text-cyan-200">Audit Required</p>
          </div>

          <div className="rounded-3xl border border-white/10 bg-black/30 p-5">
            <p className="text-xs font-black uppercase tracking-[0.20em] text-zinc-400">Reserve Layer</p>
            <h3 className="mt-3 text-xl font-black text-white">Treasury Reserve</h3>
            <p className="mt-2 text-sm text-zinc-500">Future reserve buffer for risk, liquidity, and capital allocation controls.</p>
            <p className="mt-5 text-xs font-bold uppercase tracking-[0.18em] text-cyan-200">PCS Monitored</p>
          </div>
        </div>

        <div className="mt-6 rounded-2xl border border-amber-400/20 bg-amber-400/10 p-4 text-sm text-amber-100">
          Future capital pools require legal structures, compliance review, partner due diligence, audited reporting,
          treasury exposure controls, and PCS risk monitoring before any real-world deployment.
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
          <ActionCard title="Borrow FUSD" description="Mint FUSD against available tFAITH collateral." inputValue={borrowAmount} onInputChange={setBorrowAmount} placeholder="Amount" buttonLabel="Borrow FUSD" buttonClassName="bg-blue-600 hover:bg-blue-500" onClick={borrowFUSD} />
          <ActionCard title="Repay FUSD" description="Repay test debt and restore vault health." inputValue={repayAmount} onInputChange={setRepayAmount} placeholder="Amount" buttonLabel="Repay FUSD" buttonClassName="bg-yellow-600 hover:bg-yellow-500" onClick={repayFUSD} />
          <ActionCard title="Withdraw tFAITH" description="Withdraw collateral while preserving solvency." inputValue={withdrawAmount} onInputChange={setWithdrawAmount} placeholder="Amount" buttonLabel="Withdraw tFAITH" buttonClassName="bg-red-600 hover:bg-red-500" onClick={withdrawCollateral} />
          <ActionCard title="Liquidate tVault" description="Liquidate an unsafe vault using FUSD." inputValue={liquidateAddress} onInputChange={setLiquidateAddress} placeholder="User wallet address" buttonLabel="Liquidate tVault" buttonClassName="bg-rose-700 hover:bg-rose-600" onClick={liquidateVault} />
          <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-6">
            <h3 className="text-2xl font-bold">Oracle Shock Simulator</h3>
            <p className="mt-2 min-h-[48px] text-sm text-zinc-400">
              Simulate collateral price shocks and observe how vault health, liquidation risk, and PCS monitoring respond.
            </p>

            <div className="mt-5 rounded-2xl border border-purple-400/20 bg-purple-400/10 p-4">
              <p className="text-xs font-black uppercase tracking-[0.22em] text-purple-200">Risk Control Panel</p>

              <div className="mt-4 space-y-2 text-xs">
                <div className="flex justify-between gap-3">
                  <span className="text-zinc-500">Current Oracle Price</span>
                  <span className="text-white">${oraclePrice}</span>
                </div>
                <div className="flex justify-between gap-3">
                  <span className="text-zinc-500">Shock Scenario</span>
                  <span className={Number(oraclePrice) < 0.75 ? "text-orange-300" : "text-emerald-300"}>
                    {Number(oraclePrice) < 0.75 ? "tFAITH crash active" : "Stable baseline"}
                  </span>
                </div>
                <div className="flex justify-between gap-3">
                  <span className="text-zinc-500">Risk Effect</span>
                  <span className={Number(oraclePrice) < 0.75 ? "text-orange-300" : "text-emerald-300"}>
                    {Number(oraclePrice) < 0.75 ? "Liquidation pressure elevated" : "Normal collateral conditions"}
                  </span>
                </div>
                <div className="flex justify-between gap-3">
                  <span className="text-zinc-500">PCS Response</span>
                  <span className="text-cyan-100">
                    {Number(oraclePrice) < 0.75 ? "Monitor unsafe vaults" : "Maintain parameters"}
                  </span>
                </div>
              </div>
            </div>
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
            <p className="mt-1 text-zinc-400">Live on-chain events from the credit, collateral, oracle, liquidation, and PCS risk flow.</p>
          </div>
          <button onClick={loadActivity} className="rounded-2xl border border-white/10 bg-black/30 px-5 py-3 font-semibold transition hover:bg-white/10">{activityLoading ? "Loading..." : "Refresh Activity"}</button>
        </div>
        {activity.length === 0 ? (
          <div className="rounded-2xl border border-white/10 bg-black/30 p-6 text-zinc-400">No protocol activity found yet. Run the demo flow to generate collateral, credit, oracle, and liquidation events.</div>
        ) : (
          <div className="space-y-3">{activity.map((item) => <ActivityRow key={item.id} item={item} shortHash={shortHash} />)}</div>
        )}
      </section>

      <section className="rounded-3xl border border-white/10 bg-white/[0.03] p-6">
        <h2 className="text-2xl font-bold">Current Testnet Deployment Registry</h2>
        <div className="mt-5 grid gap-4 text-sm text-zinc-300 lg:grid-cols-2">
          <RegistryLine label="tFAITH" value={FAITH_TOKEN_ADDRESS} />
          <RegistryLine label="FUSD" value={FUSD_ADDRESS} />
          <RegistryLine label="tMockOracle" value={MOCK_ORACLE_ADDRESS} />
          <RegistryLine label="tVaultManager" value={VAULT_MANAGER_ADDRESS} />
          <RegistryLine label="FaithFaucet" value={FAUCET_ADDRESS} />
        </div>
      </section>

      {status && <div className="mt-8 rounded-3xl border border-white/10 bg-white/[0.03] p-5 text-lg">{status}</div>}
          <FaithEconomicControlRoom />
          <FaithCertificateControlRoom />
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



















