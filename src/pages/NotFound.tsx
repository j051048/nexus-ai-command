import { Link } from "react-router-dom";

const NotFound = () => {
  return (
    <div className="flex min-h-screen items-center justify-center bg-muted">
      <div className="text-center">
        <h1 className="mb-4 text-4xl font-bold">404</h1>
        <p className="mb-4 text-xl text-muted-foreground">抱歉，页面未找到</p>
        <Link to="/" className="text-primary underline hover:text-primary/90">
          返回首页
        </Link>
      </div>
    </div>
  );
};

export default NotFound;
