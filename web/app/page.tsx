import HomeView from "@/components/home/HomeView";
import { commodityPills, homeDataAll, releaseInfo } from "@/lib/dashboard";

export default function Home() {
  return <HomeView data={homeDataAll()} release={releaseInfo()} pills={commodityPills()} />;
}
