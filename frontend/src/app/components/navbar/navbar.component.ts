import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';

@Component({
  selector: 'app-navbar',
  standalone: true,
  imports: [CommonModule, RouterModule],
  template: `
    <header class="navbar-header">
      <div class="navbar-container">
        <a routerLink="/" class="brand-link">
          <div class="brand-icon">✨</div>
          <div class="brand-text">
            <span class="brand-name">CreateFlow <span class="accent-text">AI</span></span>
            <span class="brand-badge">MVP</span>
          </div>
        </a>

        <nav class="nav-links">
          <a routerLink="/" routerLinkActive="active" [routerLinkActiveOptions]="{exact: true}" class="nav-item">
            📊 Dashboard
          </a>
          <a routerLink="/create" routerLinkActive="active" class="nav-item btn-create">
            ⚡ New Deliverable
          </a>
        </nav>
      </div>
    </header>
  `,
  styles: [`
    .navbar-header {
      background: rgba(15, 23, 42, 0.85);
      backdrop-filter: blur(12px);
      border-bottom: 1px solid rgba(255, 255, 255, 0.1);
      position: sticky;
      top: 0;
      z-index: 100;
    }
    .navbar-container {
      max-width: 1200px;
      margin: 0 auto;
      padding: 1rem 1.5rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .brand-link {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      text-decoration: none;
      color: #f8fafc;
    }
    .brand-icon {
      font-size: 1.5rem;
      background: linear-gradient(135deg, #6366f1, #a855f7);
      width: 40px;
      height: 40px;
      display: flex;
      align-items: center;
      justify-content: center;
      border-radius: 10px;
      box-shadow: 0 4px 12px rgba(168, 85, 247, 0.3);
    }
    .brand-text {
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }
    .brand-name {
      font-size: 1.25rem;
      font-weight: 700;
      letter-spacing: -0.02em;
    }
    .accent-text {
      background: linear-gradient(135deg, #818cf8, #c084fc);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }
    .brand-badge {
      font-size: 0.65rem;
      font-weight: 700;
      padding: 0.15rem 0.4rem;
      border-radius: 4px;
      background: rgba(99, 102, 241, 0.2);
      color: #818cf8;
      border: 1px solid rgba(99, 102, 241, 0.3);
      text-transform: uppercase;
    }
    .nav-links {
      display: flex;
      align-items: center;
      gap: 1rem;
    }
    .nav-item {
      text-decoration: none;
      color: #94a3b8;
      font-size: 0.95rem;
      font-weight: 500;
      padding: 0.5rem 0.85rem;
      border-radius: 8px;
      transition: all 0.2s ease;
    }
    .nav-item:hover {
      color: #f8fafc;
      background: rgba(255, 255, 255, 0.05);
    }
    .nav-item.active {
      color: #f8fafc;
      background: rgba(99, 102, 241, 0.15);
    }
    .btn-create {
      background: linear-gradient(135deg, #6366f1, #8b5cf6);
      color: #ffffff !important;
      font-weight: 600;
      box-shadow: 0 4px 14px rgba(99, 102, 241, 0.35);
    }
    .btn-create:hover {
      transform: translateY(-1px);
      box-shadow: 0 6px 18px rgba(99, 102, 241, 0.5);
    }
  `]
})
export class NavbarComponent {}
