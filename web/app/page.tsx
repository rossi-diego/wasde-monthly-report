import HomeView from "@/components/home/HomeView";
import { commodityPills, homeDataAll, releaseInfo } from "@/lib/dashboard";
import { getInsights, getLenses } from "@/lib/data";

export default function Home() {
  return (
    <HomeView
      data={homeDataAll()}
      release={releaseInfo()}
      pills={commodityPills()}
      insights={getInsights()}
      lenses={getLenses()}
    />
  );
}
