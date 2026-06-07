import { getDefaultConfig } from "@rainbow-me/rainbowkit"
import { mainnet } from "wagmi/chains"

export const config = getDefaultConfig({
  appName: "FAITH Protocol",
  projectId: "FAITH",
  chains: [mainnet],
})