import HomeView from "@/components/home/HomeView";
import { commodityPills, homeData, releaseInfo } from "@/lib/dashboard";

export default function Home() {
  return <HomeView data={homeData()} release={releaseInfo()} pills={commodityPills()} />;
}
