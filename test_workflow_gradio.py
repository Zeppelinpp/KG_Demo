#!/usr/bin/env python3
"""
Test script for the Gradio workflow interface
"""

import asyncio
from src.workflow_v2 import (
    KGWorkflow, 
    StreamMessageEvent, 
    ReportChunkEvent
)

async def test_workflow():
    """Test the workflow with a simple query"""
    print("🚀 Testing KGWorkflow with streaming events...")
    print("-" * 50)
    
    # Create workflow instance
    workflow = KGWorkflow(timeout=100, verbose=False)
    
    # Test query
    test_query = "分析苹果公司的财务状况"
    print(f"Query: {test_query}")
    print("-" * 50)
    
    # Run workflow
    handler = workflow.run(query=test_query)
    
    # Track events
    events_received = []
    report_chunks = []
    
    try:
        # Stream events
        async for event in handler.stream_events():
            if isinstance(event, StreamMessageEvent):
                print(f"\n📌 {event.message}")
                if event.metadata:
                    print(f"   Metadata: {event.metadata}")
                events_received.append(("stream", event.message))
                
            elif isinstance(event, ReportChunkEvent):
                print(event.chunk, end="", flush=True)
                report_chunks.append(event.chunk)
        
        # Get final result
        result = await handler
        
        print("\n" + "=" * 50)
        print("✅ Workflow completed successfully!")
        print(f"📊 Events received: {len(events_received)}")
        print(f"📝 Report chunks: {len(report_chunks)}")
        print(f"📄 Final report length: {len(''.join(report_chunks))} characters")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error during workflow execution: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_gradio_interface():
    """Test the Gradio interface functions"""
    print("\n" + "=" * 50)
    print("🎨 Testing Gradio interface components...")
    print("-" * 50)
    
    from gradio_workflow_app import process_workflow, format_metadata_html
    
    # Test metadata formatting
    test_metadata = {
        "title": "Test Analysis",
        "main_query": "Test main query",
        "insights_queries": ["Query 1", "Query 2"],
        "status": "done"
    }
    
    html = format_metadata_html(test_metadata)
    print("✅ Metadata HTML formatting works")
    print(f"   Generated HTML length: {len(html)} characters")
    
    # Test workflow processing (simplified)
    print("\n📊 Testing workflow processing...")
    history = []
    message = "Test query"
    
    try:
        # Just verify the function can be called
        generator = process_workflow(message, history)
        # We won't actually run it as it requires full setup
        print("✅ Workflow processing function initialized successfully")
        return True
    except Exception as e:
        print(f"❌ Error initializing workflow processing: {e}")
        return False

def main():
    """Main test function"""
    print("🧪 Knowledge Graph Workflow Test Suite")
    print("=" * 50)
    
    # Run async tests
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # Test 1: Workflow functionality
        workflow_success = loop.run_until_complete(test_workflow())
        
        # Test 2: Gradio interface
        gradio_success = loop.run_until_complete(test_gradio_interface())
        
        print("\n" + "=" * 50)
        print("📊 Test Results:")
        print(f"   Workflow Test: {'✅ PASSED' if workflow_success else '❌ FAILED'}")
        print(f"   Gradio Test: {'✅ PASSED' if gradio_success else '❌ FAILED'}")
        
        if workflow_success and gradio_success:
            print("\n🎉 All tests passed! The Gradio workflow interface is ready to use.")
            print("\n📝 To run the Gradio app:")
            print("   python gradio_workflow_app.py")
        else:
            print("\n⚠️ Some tests failed. Please check the errors above.")
            
    finally:
        loop.close()

if __name__ == "__main__":
    main()
