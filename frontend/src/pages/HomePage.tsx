import { useCallback, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BasicTools } from '../components/home/BasicTools';
import { HeroBanner } from '../components/home/HeroBanner';
import { KnowledgeStats } from '../components/home/KnowledgeStats';
import { RecentTasks } from '../components/home/RecentTasks';
import { SmartBidCard } from '../components/home/SmartBidCard';
import { BidVolumeOverview } from '../components/home/BidVolumeOverview';
import { BidWorkflow } from '../components/workflow/BidWorkflow';

export function HomePage(): JSX.Element {
  const navigate = useNavigate();
  const openFilePickerRef = useRef<() => void>(() => undefined);
  const [recentRefreshKey, setRecentRefreshKey] = useState(0);

  const registerFilePicker = useCallback((openFilePicker: () => void) => {
    openFilePickerRef.current = openFilePicker;
  }, []);

  return (
    <div className="home-shell">
      <HeroBanner />
      <SmartBidCard
        onPrimaryAction={() => openFilePickerRef.current()}
        onTechnicalAction={() => navigate('/history')}
        onBusinessAction={() => navigate('/knowledge')}
      />
      <BidVolumeOverview />
      <div className="grid grid-cols-[1fr_1.08fr] gap-4 max-[1500px]:grid-cols-1">
        <BasicTools />
        <RecentTasks refreshKey={recentRefreshKey} />
      </div>
      <KnowledgeStats />
      <BidWorkflow onReady={registerFilePicker} onTaskChanged={() => setRecentRefreshKey(key => key + 1)} />
    </div>
  );
}
