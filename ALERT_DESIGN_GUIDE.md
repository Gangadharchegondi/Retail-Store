# Alert Notification Design Guide

## Overview
The alert notification system has been redesigned with a modern, attractive, and simple aesthetic. The new design features gradient backgrounds, smooth animations, improved typography, and interactive close buttons.

---

## Alert Variants

### 1. **Success Alert**
```html
<div class="alert alert-success">
    <div class="alert-icon">✓</div>
    <div class="alert-content">
        <div class="alert-title">Success</div>
        <div class="alert-message">Your action was completed successfully</div>
    </div>
    <button class="alert-close" onclick="this.closest('.alert').classList.add('dismissing'); setTimeout(() => this.closest('.alert').remove(), 300);">✕</button>
</div>
```
- **Color**: Emerald Green (#10b981)
- **Background**: Subtle gradient with 12% opacity
- **Use Case**: Successful transactions, confirmations, completed actions

### 2. **Danger Alert**
```html
<div class="alert alert-danger">
    <div class="alert-icon">✕</div>
    <div class="alert-content">
        <div class="alert-title">Error</div>
        <div class="alert-message">An error occurred during processing</div>
    </div>
    <button class="alert-close" onclick="this.closest('.alert').classList.add('dismissing'); setTimeout(() => this.closest('.alert').remove(), 300);">✕</button>
</div>
```
- **Color**: Red (#ef4444)
- **Background**: Subtle gradient with 12% opacity
- **Use Case**: Errors, failures, validation issues

### 3. **Warning Alert**
```html
<div class="alert alert-warning">
    <div class="alert-icon">⚠</div>
    <div class="alert-content">
        <div class="alert-title">Warning</div>
        <div class="alert-message">Please review this important information</div>
    </div>
    <button class="alert-close" onclick="this.closest('.alert').classList.add('dismissing'); setTimeout(() => this.closest('.alert').remove(), 300);">✕</button>
</div>
```
- **Color**: Amber (#f59e0b)
- **Background**: Subtle gradient with 12% opacity
- **Use Case**: Warnings, low stock, deprecations

### 4. **Info Alert**
```html
<div class="alert alert-info">
    <div class="alert-icon">ℹ</div>
    <div class="alert-content">
        <div class="alert-title">Information</div>
        <div class="alert-message">Here's some information you should know</div>
    </div>
    <button class="alert-close" onclick="this.closest('.alert').classList.add('dismissing'); setTimeout(() => this.closest('.alert').remove(), 300);">✕</button>
</div>
```
- **Color**: Sky Blue (#0ea5e9)
- **Background**: Subtle gradient with 12% opacity
- **Use Case**: General information, tips, announcements

---

## Key Features

### 🎨 Visual Design
- **Top Border**: 3px colored accent at the top (instead of left border)
- **Gradient Background**: Subtle linear gradient (135°) with 12% and 5% opacity
- **Backdrop Filter**: Glassmorphic effect with 10px blur
- **Shadow**: Soft shadow (0 4px 16px with 8% opacity)
- **Border Radius**: Extra large (1rem) for modern look

### ✨ Animations
- **Entrance**: Smooth slideIn animation (0.4s, cubic-bezier)
- **Hover**: Subtle lift effect with enhanced shadow
- **Exit**: Smooth fade-out when dismissed
- **Icon Background**: Semi-transparent colored background for icons

### 🎯 Interactive Elements
- **Close Button**: Positioned on the right, smooth transitions
- **Hover Effects**: Lift animation, shadow enhancement, opacity change
- **Dismissible**: Remove button with smooth 300ms exit animation
- **Focus States**: Accessible focus outlines for keyboard navigation

---

## Usage Examples

### JavaScript Toast Manager
```javascript
// Show success message
toast.success("Order placed successfully!");

// Show error message
toast.error("Failed to process payment");

// Show warning message
toast.warning("Stock running low");

// Show info message
toast.info("New products available");

// With custom duration (0 = never dismiss)
toast.success("Saved!", 2000);
```

### HTML Direct Implementation
For page-level alerts that persist:
```html
<div class="alert alert-success">
    <div class="alert-icon">✓</div>
    <div class="alert-content">
        <div class="alert-title">Account Updated</div>
        <div class="alert-message">Your profile has been updated successfully</div>
    </div>
    <button class="alert-close">✕</button>
</div>
```

---

## Utility Classes

### Layout Variants

#### 1. **Full Width** (`.alert-full`)
Removes margins and border radius for full-width display
```html
<div class="alert alert-success alert-full">...</div>
```

#### 2. **Inline** (`.alert-inline`)
Reduced padding and smaller font for inline content
```html
<div class="alert alert-info alert-inline">...</div>
```

#### 3. **Compact** (`.alert-compact`)
Minimal spacing, smaller icon, reduced font size
```html
<div class="alert alert-success alert-compact">...</div>
```

#### 4. **Floating** (`.alert-floating`)
Fixed position toast-like behavior (top-right on desktop, bottom on mobile)
```html
<div class="alert alert-success alert-floating">...</div>
```

#### 5. **Block** (`.alert-block`)
Large, prominent alert with gradient background
```html
<div class="alert alert-warning alert-block">...</div>
```

### Stacking Multiple Alerts
```html
<div class="alert-stack">
    <div class="alert alert-success">...</div>
    <div class="alert alert-info">...</div>
    <div class="alert alert-warning">...</div>
</div>
```

---

## Accessibility

- ✅ Semantic HTML structure
- ✅ Proper color contrast ratios
- ✅ Keyboard accessible close button
- ✅ Focus states for all interactive elements
- ✅ Icon + text for clarity (no icon-only information)
- ✅ Dismissable alerts include visible close button

---

## Responsive Behavior

### Desktop
- Fixed position: Top-right
- Max width: 420px
- Full spacing and interactive elements

### Mobile (< 640px)
- Position: Bottom of screen
- Full width with margins
- All touch-friendly sizes maintained

---

## Color Palette

| Type | Color | Hex | Background | Icon Background |
|------|-------|-----|-----------|-----------------|
| Success | Emerald | #10b981 | rgba(16, 185, 129, 0.12) | rgba(16, 185, 129, 0.2) |
| Danger | Red | #ef4444 | rgba(239, 68, 68, 0.12) | rgba(239, 68, 68, 0.2) |
| Warning | Amber | #f59e0b | rgba(245, 158, 11, 0.12) | rgba(245, 158, 11, 0.2) |
| Info | Sky Blue | #0ea5e9 | rgba(14, 165, 233, 0.12) | rgba(14, 165, 233, 0.2) |

---

## Animation Details

### Slide In (Entrance)
```
Duration: 0.4s
Timing: cubic-bezier(0.34, 1.56, 0.64, 1)
Path: -16px (up) → 0px
Opacity: 0 → 1
```

### Dismiss (Exit)
```
Duration: 0.3s
Timing: ease
Path: 0px → -16px (up)
Opacity: 1 → 0
Class: .dismissing
```

### Hover (Interaction)
```
Duration: 0.3s
Transform: translateY(-1px)
Shadow: Enhanced to 0 8px 24px
```

---

## Best Practices

1. **Clear Messaging**: Always include both a title and message for clarity
2. **Appropriate Icon**: Use correct icon for each alert type
3. **Duration**: Success messages auto-dismiss after 3s, errors remain longer
4. **Placement**: Use floating alerts for transient feedback, inline for page-level messages
5. **Styling**: Don't override color utilities; use provided variants instead
6. **Accessibility**: Always provide both visual and text cues

---

## Browser Support

- ✅ Chrome/Edge 90+
- ✅ Firefox 88+
- ✅ Safari 14+
- ✅ Mobile browsers (iOS Safari, Chrome Mobile)

---

## Files Modified

1. **static/css/main.css** - New alert styles and utilities
2. **static/js/toast.js** - Updated toast manager with new structure
3. **frontend/templates/COMPONENTS_REFERENCE.html** - Updated component examples

---

Last Updated: 2024
