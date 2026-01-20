import uiautomation as auto
import time
import sys

def get_foreground_window_rect():
    """
    Return the foreground window bounding rectangle as a dict:
    {name,left,top,right,bottom,width,height}

    Note: coordinates are returned in the same screen coordinate space as
    UIAutomation's BoundingRectangle (often physical pixels depending on DPI).
    """
    try:
        window = auto.GetForegroundWindow()
        if not window:
            return None
        rect = window.BoundingRectangle
        w = int(rect.width())
        h = int(rect.height())
        if w <= 1 or h <= 1:
            return None
        return {
            "name": getattr(window, "Name", "Unknown"),
            "left": int(rect.left),
            "top": int(rect.top),
            "right": int(rect.right),
            "bottom": int(rect.bottom),
            "width": w,
            "height": h,
        }
    except Exception:
        return None

def get_ui_tree_summary(max_elements=70):
    """
    Captures interactive elements from the foreground window and returns a text summary.
    Coordinates are normalized to 0-1000 (default: relative to full screen).
    """
    try:
        # Get the screen size for normalization
        from tools import get_screen_size
        screen_width, screen_height = get_screen_size()
        
        window = auto.GetForegroundWindow()
        if not window:
            return "No foreground window detected."

        window_name = getattr(window, 'Name', 'Unknown')
        win_rect = window.BoundingRectangle
        win_w = int(win_rect.width())
        win_h = int(win_rect.height())
        found_elements = []
        
        # Priority types
        priority_types = [
            auto.ControlType.ButtonControl,
            auto.ControlType.EditControl,
            auto.ControlType.MenuItemControl,
            auto.ControlType.HyperlinkControl,
            auto.ControlType.ComboBoxControl,
            auto.ControlType.TabItemControl,
        ]
        
        # Info types
        info_types = [
            auto.ControlType.ListItemControl,
            auto.ControlType.TextControl,
            auto.ControlType.TreeItemControl,
            auto.ControlType.MenuBarControl
        ]

        def walk(control, depth=0):
            if depth > 6 or len(found_elements) >= max_elements:
                return
            
            try:
                # Get basic info
                name = getattr(control, 'Name', '')
                ctype = control.ControlType
                ctype_name = control.ControlTypeName.replace("Control", "")
                
                is_valid = False
                if ctype in priority_types:
                    is_valid = True
                elif ctype in info_types and name and len(name.strip()) > 1:
                    is_valid = True
                
                if is_valid:
                    rect = control.BoundingRectangle
                    if rect.width() > 2 and rect.height() > 2:
                        center_x = rect.left + (rect.width() // 2)
                        center_y = rect.top + (rect.height() // 2)

                        # By default, normalize to full screen. If the foreground window rect
                        # looks sane, also compute window-relative coordinates and include both.
                        nx = int((center_x / screen_width) * 1000)
                        ny = int((center_y / screen_height) * 1000)

                        wx = None
                        wy = None
                        try:
                            if win_w > 10 and win_h > 10:
                                wx = int(((center_x - win_rect.left) / win_w) * 1000)
                                wy = int(((center_y - win_rect.top) / win_h) * 1000)
                        except Exception:
                            wx = None
                            wy = None
                        
                        nx = max(0, min(1000, nx))
                        ny = max(0, min(1000, ny))
                        if wx is not None and wy is not None:
                            wx = max(0, min(1000, wx))
                            wy = max(0, min(1000, wy))
                        
                        # De-duplicate: don't add if we have the same name and type very close
                        duplicate = False
                        for e in found_elements:
                            if e['name'] == name and e['type'] == ctype_name:
                                if abs(e['x'] - nx) < 5 and abs(e['y'] - ny) < 5:
                                    duplicate = True
                                    break
                        
                        if not duplicate:
                            found_elements.append({
                                "name": name,
                                "type": ctype_name,
                                "x": nx,
                                "y": ny,
                                # Window-relative coords (when available). These help when the
                                # agent uses a cropped screenshot of the foreground window.
                                "wx": wx,
                                "wy": wy,
                            })
            except Exception:
                pass

            try:
                # Walk children
                for child in control.GetChildren():
                    walk(child, depth + 1)
            except Exception:
                pass

        walk(window)
        
        if not found_elements:
            # Try one more time with a slightly different approach if we found nothing
            return f"Window: {window_name}\nNo interactive UI elements detected."

        # Sort elements by Y then X to make it more readable for the LLM
        found_elements.sort(key=lambda e: (e['y'], e['x']))

        summary = [f"Foreground Window: {window_name}", "Detected UI Elements:"]
        for el in found_elements:
            name_str = f'"{el["name"]}"' if el["name"] else "Unnamed"
            # Include both coordinate spaces when we have them.
            if el.get("wx") is not None and el.get("wy") is not None:
                summary.append(
                    f"- {el['type']}: {name_str} at screen=({el['x']}, {el['y']}), window=({el['wx']}, {el['wy']})"
                )
            else:
                summary.append(f"- {el['type']}: {name_str} at screen=({el['x']}, {el['y']})")
            
        return "\n".join(summary)

    except Exception as e:
        return f"Metadata error: {str(e)}"

if __name__ == "__main__":
    # Wait a bit so user can switch window if they want to test
    print("Capturing in 2 seconds...")
    time.sleep(2)
    print(get_ui_tree_summary())
