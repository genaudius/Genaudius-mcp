import sys
import json
from music21 import converter, stream, midi, instrument

def final_mixer(clusters_data):
    """
    Mixes parts from all 3 Clusters (Percussion, Harmony, Vocals).
    clusters_data: List of objects from all session recordings in Supabase.
    """
    score = stream.Score()
    
    # Track grouping for General MIDI compliance
    # Harmony: 1-9, Percussion: 10, Vocals: 11-16
    
    for part in clusters_data:
        role = part.get("instrument_role", "unknown")
        abc = part.get("part_abc", "")
        cluster = part.get("cluster_id", "harmony")
        
        try:
            p = converter.parse(abc, format='abc')
            p.id = role
            
            # Basic MIDI Channel Assignment
            if cluster == "percussion":
                # In music21/MIDI, channel 10 is usually for percussion
                for el in p.recurse():
                    if hasattr(el, 'channel'):
                        el.channel = 10
            
            score.insert(0, p)
        except Exception as e:
            print(f"Error mixing {role}: {e}", file=sys.stderr)
            
    return score

if __name__ == "__main__":
    try:
        raw_input = sys.stdin.read()
        if not raw_input:
            sys.exit(1)
            
        data = json.loads(raw_input)
        # Expected: List of all parts from recording_sessions for this session_id
        mixed_score = final_mixer(data)
        
        output_file = "final_production.mid"
        mf = midi.translate.streamToMidiFile(mixed_score)
        mf.open(output_file, 'wb')
        mf.write()
        mf.close()
        
        print(f"Production Finalized: {output_file}")
        
    except Exception as e:
        print(f"Mixer Error: {e}", file=sys.stderr)
        sys.exit(1)
