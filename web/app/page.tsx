import HomeView from "@/components/home/HomeView";
import { homeDataAll, releaseInfo } from "@/lib/dashboard";
import { getInsights, getLenses } from "@/lib/data";

export default function Home() {
  return <HomeView data={homeDataAll()} release={releaseInfo()} insights={getInsights()} lenses={getLenses()} />;
}
