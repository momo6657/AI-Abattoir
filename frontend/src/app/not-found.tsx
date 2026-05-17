import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center py-20">
      <h2 className="text-6xl font-bold text-gray-600 mb-4">404</h2>
      <p className="text-xl text-gray-400 mb-8">页面未找到</p>
      <Link href="/" className="bg-blue-600 hover:bg-blue-700 px-6 py-3 rounded-lg">
        返回首页
      </Link>
    </div>
  );
}
