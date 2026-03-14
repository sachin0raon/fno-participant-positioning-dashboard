import { Outlet } from 'react-router'
import { Header } from './Header'

export function Root() {
  return (
    <div className="min-h-screen relative overflow-hidden">
      {/* Ambient background orbs */}
      <div className="fixed inset-0 -z-10 pointer-events-none">
        <div className="absolute top-[-20%] left-[-10%] w-[600px] h-[600px] rounded-full bg-violet-600/[0.07] blur-[120px]" />
        <div className="absolute bottom-[-15%] right-[-10%] w-[500px] h-[500px] rounded-full bg-fuchsia-600/[0.05] blur-[100px]" />
        <div className="absolute top-[40%] right-[20%] w-[300px] h-[300px] rounded-full bg-indigo-600/[0.04] blur-[80px]" />
      </div>

      <Header />
      <main className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-6 pb-16">
        <Outlet />
      </main>
    </div>
  )
}
