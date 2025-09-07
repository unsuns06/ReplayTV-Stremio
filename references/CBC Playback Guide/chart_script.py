import plotly.graph_objects as go
import plotly.io as pio
import numpy as np

# Create a comprehensive flowchart for CBC Gem Stremio Addon
fig = go.Figure()

# Define colors for different components as specified
colors = {
    'user': '#1FB8CD',      # Blue for user interactions
    'auth': '#2E8B57',      # Green for authentication steps
    'content': '#D2BA4C',   # Orange for content discovery
    'stream': '#DB4545',    # Red for stream resolution
    'cache': '#944454'      # Purple for caching/storage (using proper purple from palette)
}

# Define nodes with better positioning for compact layout
nodes = [
    # User Configuration Flow (Column 1)
    {'text': 'User visits<br>/configure', 'x': 1, 'y': 10, 'color': colors['user'], 'shape': 'circle'},
    {'text': 'Enter CBC<br>credentials', 'x': 1, 'y': 9, 'color': colors['user'], 'shape': 'circle'},
    {'text': 'Get install URL<br>with config', 'x': 1, 'y': 8, 'color': colors['user'], 'shape': 'circle'},
    {'text': 'Install addon<br>in Stremio', 'x': 1, 'y': 7, 'color': colors['user'], 'shape': 'circle'},
    
    # Authentication Flow (Column 2)
    {'text': 'Fetch ROPC<br>settings', 'x': 2.5, 'y': 9.5, 'color': colors['auth'], 'shape': 'circle'},
    {'text': 'OAuth 2.0<br>ROPC login', 'x': 2.5, 'y': 8.5, 'color': colors['auth'], 'shape': 'circle'},
    {'text': 'Get refresh &<br>access tokens', 'x': 2.5, 'y': 7.5, 'color': colors['auth'], 'shape': 'circle'},
    {'text': 'Get claims<br>token', 'x': 2.5, 'y': 6.5, 'color': colors['auth'], 'shape': 'circle'},
    {'text': 'Cache all<br>tokens', 'x': 2.5, 'y': 5.5, 'color': colors['cache'], 'shape': 'circle'},
    
    # Content Access Flow (Column 3)
    {'text': 'Stremio requests<br>content', 'x': 4, 'y': 10, 'color': colors['content'], 'shape': 'circle'},
    {'text': 'Extract config<br>from URL path', 'x': 4, 'y': 9, 'color': colors['content'], 'shape': 'circle'},
    {'text': 'Initialize<br>CBCAuth', 'x': 4, 'y': 8, 'color': colors['content'], 'shape': 'circle'},
    
    # Decision point for token validity (diamond shape)
    {'text': 'Tokens<br>valid?', 'x': 4, 'y': 7, 'color': colors['cache'], 'shape': 'diamond'},
    
    {'text': 'Refresh tokens<br>if needed', 'x': 3, 'y': 6, 'color': colors['auth'], 'shape': 'circle'},
    {'text': 'Make auth CBC<br>API requests', 'x': 4, 'y': 6, 'color': colors['content'], 'shape': 'circle'},
    {'text': 'Return content<br>to Stremio', 'x': 4, 'y': 5, 'color': colors['content'], 'shape': 'circle'},
    
    # Stream Resolution Flow (Column 4)
    {'text': 'User selects<br>content', 'x': 5.5, 'y': 10, 'color': colors['stream'], 'shape': 'circle'},
    {'text': 'Parse show ID<br>from request', 'x': 5.5, 'y': 9, 'color': colors['stream'], 'shape': 'circle'},
    {'text': 'Fetch metadata<br>from catalog', 'x': 5.5, 'y': 8, 'color': colors['stream'], 'shape': 'circle'},
    {'text': 'Extract media ID<br>for episode', 'x': 5.5, 'y': 7, 'color': colors['stream'], 'shape': 'circle'},
    {'text': 'Request stream<br>with claims', 'x': 5.5, 'y': 6, 'color': colors['stream'], 'shape': 'circle'},
    {'text': 'Return HLS<br>stream URL', 'x': 5.5, 'y': 5, 'color': colors['stream'], 'shape': 'circle'},
    
    # Error handling
    {'text': 'Auth Error<br>Handler', 'x': 1.5, 'y': 5, 'color': colors['auth'], 'shape': 'circle'},
]

# Add nodes with different shapes
for i, node in enumerate(nodes):
    if node['shape'] == 'diamond':
        # Create diamond shape for decision points
        diamond_x = [node['x']-0.25, node['x'], node['x']+0.25, node['x'], node['x']-0.25]
        diamond_y = [node['y'], node['y']+0.3, node['y'], node['y']-0.3, node['y']]
        
        fig.add_trace(go.Scatter(
            x=diamond_x, 
            y=diamond_y, 
            fill='toself',
            fillcolor=node['color'],
            mode='lines',
            line=dict(width=2, color='white'),
            showlegend=False,
            hoverinfo='none'
        ))
        
        # Add text for diamond
        fig.add_trace(go.Scatter(
            x=[node['x']], 
            y=[node['y']], 
            mode='text',
            text=node['text'],
            textfont=dict(size=11, color='white'),
            showlegend=False,
            hoverinfo='none'
        ))
    else:
        # Regular circular nodes
        fig.add_trace(go.Scatter(
            x=[node['x']], 
            y=[node['y']], 
            mode='markers+text',
            marker=dict(size=80, color=node['color'], line=dict(width=2, color='white')),
            text=node['text'],
            textposition='middle center',
            textfont=dict(size=11, color='white', family='Arial Black'),
            showlegend=False,
            hoverinfo='none'
        ))

# Define connections with better flow paths
connections = [
    # User configuration flow
    (0, 1), (1, 2), (2, 3),
    
    # From user config to auth
    (1, 4), (4, 5), (5, 6), (6, 7), (7, 8),
    
    # Content access flow
    (9, 10), (10, 11), (11, 12),
    
    # Decision paths from token validity check
    (12, 13), (13, 8), (8, 14),  # Refresh path
    (12, 14), (14, 15),  # Valid tokens path
    
    # Stream resolution flow
    (16, 17), (17, 18), (18, 19), (19, 20), (20, 21),
    
    # Error handling
    (13, 22), (5, 22),  # Auth errors to handler
    
    # Cross-flow connections
    (3, 9), (15, 16),  # Connect flows
]

# Add connection lines with better styling
for start_idx, end_idx in connections:
    start_node = nodes[start_idx]
    end_node = nodes[end_idx]
    
    # Determine line style based on connection type
    if 'Error' in start_node['text'] or 'Error' in end_node['text']:
        line_color = '#DB4545'
        line_dash = 'dash'
    elif start_node['color'] == end_node['color']:
        line_color = start_node['color']
        line_dash = 'solid'
    else:
        line_color = '#666666'
        line_dash = 'solid'
    
    fig.add_trace(go.Scatter(
        x=[start_node['x'], end_node['x']],
        y=[start_node['y'], end_node['y']],
        mode='lines',
        line=dict(width=3, color=line_color, dash=line_dash),
        showlegend=False,
        hoverinfo='none'
    ))

# Add directional arrows at key points
arrow_configs = [
    # Main flow arrows
    {'x': 1, 'y': 9.5, 'direction': 'down'},
    {'x': 1, 'y': 8.5, 'direction': 'down'},
    {'x': 1, 'y': 7.5, 'direction': 'down'},
    
    {'x': 2.5, 'y': 9, 'direction': 'down'},
    {'x': 2.5, 'y': 8, 'direction': 'down'},
    {'x': 2.5, 'y': 7, 'direction': 'down'},
    {'x': 2.5, 'y': 6, 'direction': 'down'},
    
    {'x': 4, 'y': 9.5, 'direction': 'down'},
    {'x': 4, 'y': 8.5, 'direction': 'down'},
    {'x': 4, 'y': 7.5, 'direction': 'down'},
    {'x': 4, 'y': 6.5, 'direction': 'down'},
    {'x': 4, 'y': 5.5, 'direction': 'down'},
    
    {'x': 5.5, 'y': 9.5, 'direction': 'down'},
    {'x': 5.5, 'y': 8.5, 'direction': 'down'},
    {'x': 5.5, 'y': 7.5, 'direction': 'down'},
    {'x': 5.5, 'y': 6.5, 'direction': 'down'},
    {'x': 5.5, 'y': 5.5, 'direction': 'down'},
    
    # Cross-flow arrows
    {'x': 1.8, 'y': 9.2, 'direction': 'right'},
    {'x': 2.3, 'y': 9.2, 'direction': 'right'},
    {'x': 4.8, 'y': 9.5, 'direction': 'right'},
]

# Add arrows
for arrow in arrow_configs:
    if arrow['direction'] == 'down':
        ay_offset = 0.15
        ax_offset = 0
    elif arrow['direction'] == 'right':
        ay_offset = 0
        ax_offset = -0.15
    else:
        ay_offset = 0
        ax_offset = 0
    
    fig.add_annotation(
        x=arrow['x'],
        y=arrow['y'],
        ax=arrow['x'] + ax_offset,
        ay=arrow['y'] + ay_offset,
        arrowhead=2,
        arrowsize=1.5,
        arrowwidth=2,
        arrowcolor="#333333",
        showarrow=True
    )

# Add labels for decision paths
fig.add_annotation(
    x=3.5, y=6.7,
    text="Invalid",
    showarrow=False,
    font=dict(size=10, color="#666666")
)

fig.add_annotation(
    x=4.3, y=6.7,
    text="Valid",
    showarrow=False,
    font=dict(size=10, color="#666666")
)

# Create legend with proper colors
legend_items = [
    {'name': 'User Interact', 'color': colors['user']},
    {'name': 'Auth Steps', 'color': colors['auth']},
    {'name': 'Content Disc', 'color': colors['content']},
    {'name': 'Stream Res', 'color': colors['stream']},
    {'name': 'Cache/Store', 'color': colors['cache']}
]

for i, item in enumerate(legend_items):
    fig.add_trace(go.Scatter(
        x=[None], y=[None],
        mode='markers',
        marker=dict(size=20, color=item['color']),
        name=item['name'],
        showlegend=True
    ))

# Update layout with better spacing
fig.update_layout(
    title="CBC Addon Auth & Stream Flow",
    xaxis=dict(
        range=[0.5, 6],
        showgrid=False,
        showticklabels=False,
        zeroline=False
    ),
    yaxis=dict(
        range=[4.5, 10.5],
        showgrid=False,
        showticklabels=False,
        zeroline=False
    ),
    plot_bgcolor='white',
    legend=dict(
        orientation='h',
        yanchor='bottom',
        y=1.05,
        xanchor='center',
        x=0.5
    )
)

fig.update_traces(cliponaxis=False)

# Save the chart
fig.write_image("cbc_addon_flowchart.png")