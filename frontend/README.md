# ChainSAHYOG — Frontend (VASP Attribution Dashboard & Visual Showcase)

Modern, forensic-grade React application for law-enforcement blockchain intelligence (SIH26182). Built with **React 19**, **Vite**, **Tailwind CSS v4**, **GSAP 3** + `@gsap/react`, and **Cytoscape.js**.

---

## Route Architecture

| Route | View | Description |
| :--- | :--- | :--- |
| **`/`** | **`LandingPage.jsx`** | High-impact visual landing page explaining the core problem with interactive GSAP animations, constellation background, live case study simulation, laundering typologies breakdown, and quick investigation launch. |
| **`/dashboard`** | **`DashboardPage.jsx`** | Full forensic investigation console with multi-hop Cytoscape graph visualizer, slide-in node/edge inspector drawer, FIFO taint tracker, Section 91 CrPC notice generator, and court-ready PDF download. Supports deep-linking via query parameters (`?address=0x...&chain=1`). |

---

## Key Capabilities

### 1. Root Landing Page (`/`)
- **Fluid GSAP Motion Engine**:
  - **Constellation Background Canvas**: Lightweight particle network illustrating live EVM transaction flows with subtle cursor repulsion.
  - **Interactive 4-Stage Heist Visualizer**: Stepped interactive walkthrough demonstrating:
    1. *The Theft*: Unhosted suspect wallet with zero KYC.
    2. *The Fog*: Peel chains and smurfing across 12 burner wallets (demonstrating why chasing anonymous wallets is a dead end).
    3. *The Breakthrough*: Regulated exchange chokepoint (Binance deposit hub identified with 88% confidence).
    4. *The Takedown*: Section 91 CrPC statutory freeze order served via SAHYOG to unmask KYC.
  - **The Paradigm Shift Section**: Highlighting the futility of chasing disposable burner wallets vs the power of targeting regulated exchange chokepoints.
  - **Interactive Typology Showcase**: Interactive SVG diagrams of Peel Chains, Layering, Structuring (Smurfing), and Rapid Pass-Through Conduits with mathematical detection rules.
  - **Engine Capabilities & 5-Step Workflow**: Detailed LEA operational pipeline from incident intake to asset freezing.

### 2. Forensic Investigation Console (`/dashboard`)
- **Interactive Multi-Asset Cytoscape Graph**: Directed graph representation of multi-hop fund flows with shortest-path lighting, zoom, fit, and node/edge inspection.
- **Dynamic Confidence Meter**: Animated SVG radial gauge with an ease-interpolated numeric counter and expandable additive breakdown (+50 known label, +23 distance, +15 clean path).
- **FIFO Taint Math**: Real-time progress bar of suspect-attributed funds vs unobserved wallet balances (*Clayton's Case* legal accounting).
- **Entity Resolution & Clustering**: Visualizes exchange deposit sweeps and addresses consolidated under the minimum hop-distance rule ($\min(\text{depth})$).
- **Sanctions & Risk Flags**: Flags OFAC SDN list entities, Tornado Cash / mixers, and cross-chain bridges.
- **Section 91 CrPC Notice Generator**: Formatted modal for immediate law-enforcement requisition serving under Section 91 CrPC / Section 94 BNSS.
- **Court-Ready PDF Reports**: 1-click download of cryptographic PDF reports from `/report`.

---

## Directory Structure

```
frontend/
├── src/
│   ├── api/
│   │   └── client.js             # API client (health, demos, trace, report)
│   ├── components/
│   │   ├── Navbar.jsx            # Dynamic navigation for landing vs dashboard
│   │   ├── SearchBar.jsx         # EVM address input, depth slider, dust floor, mode selector
│   │   ├── DemoChips.jsx         # Staggered GSAP demo selector
│   │   ├── LoadingRadar.jsx      # Multi-phase radar scanner animation
│   │   ├── TraceGraph.jsx        # Cytoscape graph canvas with controls & path highlighting
│   │   ├── NodeDrawer.jsx        # Slide-in forensic inspection drawer
│   │   ├── FindingPanel.jsx      # Master findings dashboard (Overview, Forensics, Trail)
│   │   ├── SahyogModal.jsx       # Section 91 CrPC notice generator modal
│   │   ├── Toast.jsx             # Animated alert notifications
│   │   ├── landing/              # Modular landing page sections
│   │   │   ├── BackgroundCanvas.jsx        # Constellation particle background
│   │   │   ├── HeroSection.jsx             # Masthead, quick-launch bar, live metrics
│   │   │   ├── InteractiveHeistVisualizer.jsx # 4-stage interactive heist simulation
│   │   │   ├── ProblemSolutionSection.jsx  # Paradigm shift comparison cards
│   │   │   ├── TypologiesShowcase.jsx      # Interactive laundering typologies visualizer
│   │   │   ├── EngineCapabilitiesSection.jsx # 6 core forensic pillars
│   │   │   ├── WorkflowSection.jsx         # 5-step investigative workflow
│   │   │   └── LandingFooter.jsx           # SIH26182 / I4C attribution footer
│   │   └── findings/
│   │       ├── HeadlineCard.jsx  # Hero attribution banner
│   │       ├── ConfidenceMeter.jsx # SVG radial meter & arithmetic breakdown
│   │       ├── TaintCard.jsx     # FIFO taint progress & balance accounting
│   │       ├── TypologiesCard.jsx# Laundering typologies (Peel, Layering, Structuring)
│   │       ├── ClustersCard.jsx  # Entity resolution & deposit consolidation
│   │       ├── RiskFlagsCard.jsx # OFAC, mixers, and bridges
│   │       ├── PathTimeline.jsx  # Hop-by-hop breadcrumb trail
│   │       └── TokenWarningsCard.jsx # Contract pinning & impersonation warnings
│   ├── pages/
│   │   ├── LandingPage.jsx       # Root route (/)
│   │   └── DashboardPage.jsx     # Console route (/dashboard)
│   ├── utils/
│   │   ├── formatters.js         # Currency, address ellipsis, and timestamp formatters
│   │   ├── graphStyle.js         # Cytoscape stylesheet and layout configuration
│   │   └── pathfinder.js         # BFS traversal and primary path extraction
│   ├── App.jsx                   # React Router & lazy code-splitting
│   ├── main.jsx                  # React DOM entrypoint
│   └── index.css                 # Tailwind CSS v4 styling rules
├── vite.config.js                # Vite configuration with Tailwind v4 & /api proxy
└── package.json
```

---

## Development & Usage

### 1. Install Dependencies
```bash
npm install
```

### 2. Run Development Server
```bash
npm run dev
```
The dev server starts on `http://localhost:5173`. API requests to `/api` are automatically proxied to the backend at `http://127.0.0.1:8000`.

### 3. Production Build & Linting
```bash
npm run lint
npm run build
npm run preview
```
