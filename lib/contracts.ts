export const FAITH_TOKEN_ADDRESS =
  "0x25131C5655DBB24B768bEb8cE4A135E0ED3836FA";

export const FUSD_ADDRESS =
  "0x35Ac0De590E8C2280464027aBdab93e6b0E199a0";

export const MOCK_ORACLE_ADDRESS =
  "0x7125fe3424Ba0796B2A45b450e295c93a18224c7";

export const VAULT_MANAGER_ADDRESS =
  "0x76849F654906F4956fff0d3B2b10eE97ce4d0d4B";

export const FAUCET_ADDRESS =
  "0x4bC22b996631ff28617ed5EDeA17f741Ff466c14";

export const FAITH_TOKEN_ABI = [
  "function balanceOf(address account) view returns (uint256)",
  "function approve(address spender, uint256 amount) returns (bool)",
];

export const FUSD_ABI = [
  "function balanceOf(address account) view returns (uint256)",
  "function totalSupply() view returns (uint256)",
  "function approve(address spender, uint256 amount) returns (bool)",
];

export const MOCK_ORACLE_ABI = [
  "function getPrice() view returns (uint256)",
  "function setPrice(uint256 _price)",
  "event PriceUpdated(uint256 previousPrice, uint256 newPrice)",
];

export const VAULT_MANAGER_ABI = [
  "function depositCollateral(uint256 amount)",
  "function withdrawCollateral(uint256 amount)",
  "function borrow(uint256 amount)",
  "function repay(uint256 amount)",
  "function liquidate(address user)",
  "function getHealthFactor(address user) view returns (uint256)",
  "function getBorrowLimit(address user) view returns (uint256)",
  "function vaults(address user) view returns (uint256 collateralAmount, uint256 debtAmount, bool active)",

  "event CollateralDeposited(address indexed user, uint256 amount, uint256 newCollateralAmount)",
  "event CollateralWithdrawn(address indexed user, uint256 amount, uint256 remainingCollateralAmount)",
  "event TfUSDBorrowed(address indexed user, uint256 amount, uint256 newDebtAmount)",
  "event TfUSDRepaid(address indexed user, uint256 amount, uint256 remainingDebtAmount)",
  "event VaultLiquidated(address indexed user, address indexed liquidator, uint256 debtRepaid, uint256 collateralSeized)",
];

export const FAUCET_ABI = [
  "function claim()",
  "function faucetBalance() view returns (uint256)",
  "function hasClaimed(address user) view returns (bool)",
];
