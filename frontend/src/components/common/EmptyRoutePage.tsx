import { Button, Result } from 'antd';
import { useNavigate } from 'react-router-dom';

export function EmptyRoutePage(): JSX.Element {
  const navigate = useNavigate();

  return (
    <div className="grid h-full place-items-center">
      <Result
        status="info"
        title="模块建设中"
        subTitle="当前单机版已优先完成首页、知识库、资信库、产品库和系统设置。"
        extra={
          <Button type="primary" onClick={() => navigate('/')}>
            返回主页
          </Button>
        }
      />
    </div>
  );
}
