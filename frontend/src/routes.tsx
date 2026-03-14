import { Root } from './components/Layout/Root'
import Dashboard from './pages/Dashboard'
import type { RouteObject } from 'react-router'

export const routes: RouteObject[] = [
  {
    path: '/',
    element: <Root />,
    children: [
      {
        index: true,
        element: <Dashboard />,
      },
    ],
  },
]
